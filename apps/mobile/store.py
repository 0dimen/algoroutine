"""Single-user local library. Immutable versions; atomic commands and revision checks."""
import hashlib
import json
import sqlite3
import uuid
import time
from contextlib import contextmanager
from datetime import datetime, timezone

class DomainError(Exception):
    def __init__(self, code, message, status=400):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)

def now():
    return datetime.now(timezone.utc).isoformat()

def uid():
    return str(uuid.uuid4())

def validate_content(value):
    if not isinstance(value, dict):
        raise DomainError('INVALID', '루틴 내용을 확인해 주세요.')
    title, steps = value.get('title'), value.get('steps')
    if not isinstance(title, str) or not title.strip() or len(title) > 200:
        raise DomainError('INVALID', '제목은 1~200자로 입력해 주세요.')
    if not isinstance(steps, list) or not 1 <= len(steps) <= 50:
        raise DomainError('INVALID', '단계를 1~50개 작성해 주세요.')
    description = value.get('description', '')
    if not isinstance(description, str) or len(description) > 5000:
        raise DomainError('INVALID', '설명은 5,000자 이내로 작성해 주세요.')
    seen = set()
    clean = []
    for step in steps:
        if not isinstance(step, dict):
            raise DomainError('INVALID', '단계를 확인해 주세요.')
        sid, label = step.get('id'), step.get('title')
        if not isinstance(sid, str) or not sid or len(sid) > 100 or sid in seen:
            raise DomainError('INVALID', '단계 식별자가 중복되거나 없습니다.')
        if not isinstance(label, str) or not label.strip() or len(label) > 300:
            raise DomainError('INVALID', '단계 제목은 1~300자로 입력해 주세요.')
        seen.add(sid)
        clean.append({'id': sid, 'title': label})
    result = {'title': title, 'description': description, 'steps': clean}
    # Optional rest duration (minutes). Absent on older definitions; starting such a routine
    # only proposes schedule changes and never applies them by itself.
    rest = value.get('restMinutes')
    if rest is not None:
        if type(rest) is not int or not 1 <= rest <= 720:
            raise DomainError('INVALID', '휴식 시간은 1~720분으로 입력해 주세요.')
        result['restMinutes'] = rest
    return result

CATALOG = [{'id': 'report-start', 'version': 1, 'title': '보고서 초안 시작',
            'description': '완벽한 문장보다 작은 첫 초안을 만듭니다.',
            'author': {'id': 'studio', 'name': '루틴 스튜디오'}, 'source': 'library',
            'steps': [{'id': 'open', 'title': '새 문서 열기'},
                      {'id': 'headings', 'title': '소제목 세 개 적기'},
                      {'id': 'first', 'title': '첫 문장 한 줄 쓰기'}]}]

class Store:
    def __init__(self, path):
        self.path = str(path)
        with self.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS definitions(id TEXT PRIMARY KEY, current_version INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS versions(definition_id TEXT, version INTEGER, body TEXT NOT NULL,
              PRIMARY KEY(definition_id,version));
            CREATE TABLE IF NOT EXISTS drafts(id TEXT PRIMARY KEY, revision INTEGER, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS commands(id TEXT PRIMARY KEY, request_hash TEXT, result TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS generated_proposals(id TEXT PRIMARY KEY, body TEXT NOT NULL, created REAL NOT NULL, accepted_id TEXT);
            CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value INTEGER);
            INSERT OR IGNORE INTO metadata VALUES('library_revision',0);
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def library(self):
        with self.connect() as db:
            # Rows and revision must describe the same complete library snapshot.
            db.execute('BEGIN')
            rows = db.execute('SELECT v.body FROM definitions d JOIN versions v ON d.id=v.definition_id AND d.current_version=v.version ORDER BY d.rowid DESC').fetchall()
            rev = db.execute("SELECT value FROM metadata WHERE key='library_revision'").fetchone()[0]
        return {'items': [json.loads(r[0]) for r in rows], 'revision': rev}

    def version(self, definition_id, version=None):
        with self.connect() as db:
            return self._version(db, definition_id, version)

    def _version(self, db, definition_id, version=None):
        if version is None:
            r = db.execute('SELECT current_version FROM definitions WHERE id=?', (definition_id,)).fetchone()
            if not r:
                raise DomainError('NOT_FOUND', '루틴을 찾을 수 없습니다.', 404)
            version = r[0]
        row = db.execute('SELECT body FROM versions WHERE definition_id=? AND version=?', (definition_id, version)).fetchone()
        if not row:
            raise DomainError('NOT_FOUND', '루틴을 찾을 수 없습니다.', 404)
        return json.loads(row[0])

    def draft(self, key):
        with self.connect() as db:
            r = db.execute('SELECT revision,body FROM drafts WHERE id=?', (key,)).fetchone()
        return {'revision': r[0], 'content': json.loads(r[1])} if r else {'revision': 0, 'content': None}

    def save_draft(self, key, expected_revision, content):
        # Incomplete drafts are allowed, but bounded and never search candidates.
        if not isinstance(key, str) or not 1 <= len(key) <= 100 or not isinstance(content, dict) or len(json.dumps(content)) > 100000:
            raise DomainError('INVALID', '초안을 확인해 주세요.')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            r = db.execute('SELECT revision FROM drafts WHERE id=?', (key,)).fetchone()
            revision = r[0] if r else 0
            if type(expected_revision) is not int or expected_revision != revision:
                raise DomainError('VERSION_CONFLICT', '다른 창에서 초안이 변경되었습니다. 입력은 유지됩니다.', 409)
            db.execute('INSERT OR REPLACE INTO drafts VALUES(?,?,?)', (key, revision+1, json.dumps(content, ensure_ascii=False)))
        return {'revision': revision+1, 'content': content}

    def propose_generated(self, content):
        clean = validate_content(content)
        proposal = dict(clean, id=uid(), version=0, source='ai',
                        author={'id':'meta-ai','name':'Meta AI'}, generated=True)
        with self.connect() as db:
            db.execute('INSERT INTO generated_proposals VALUES(?,?,?,NULL)',
                       (proposal['id'], json.dumps(proposal,ensure_ascii=False), time.time()))
        return proposal

    def command_result(self, key):
        with self.connect() as db:
            row = db.execute('SELECT result FROM commands WHERE id=?', (key,)).fetchone()
        if not row:
            raise DomainError('NOT_FOUND', '아직 저장 결과가 없습니다. 같은 요청으로 다시 확인할 수 있습니다.', 404)
        return json.loads(row[0])

    def command(self, request):
        if not isinstance(request, dict) or not isinstance(request.get('commandId'), str) or not 1 <= len(request['commandId']) <= 100:
            raise DomainError('INVALID', '저장 요청을 확인해 주세요.')
        digest = hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            previous = db.execute('SELECT request_hash,result FROM commands WHERE id=?', (request['commandId'],)).fetchone()
            if previous:
                if previous[0] != digest:
                    raise DomainError('IDEMPOTENCY_CONFLICT', '이미 사용한 요청과 내용이 다릅니다.', 409)
                return json.loads(previous[1])
            kind = request.get('kind')
            if kind == 'saveDefinition':
                clean = validate_content(request.get('content'))
                did = request.get('definitionId')
                if did:
                    old = self._version(db, did)
                    if type(request.get('expectedVersion')) is not int or request['expectedVersion'] != old['version']:
                        raise DomainError('VERSION_CONFLICT', '다른 창에서 루틴이 변경되었습니다. 초안을 유지하고 최신 내용을 확인해 주세요.', 409)
                    body = dict(old, **clean, version=old['version']+1, updatedAt=now())
                    if 'restMinutes' not in clean:
                        body.pop('restMinutes', None)
                else:
                    did = uid()
                    body = dict(clean, id=did, version=1, author={'id':'local-user','name':'나'}, source='mine', origin=None, createdAt=now())
            elif kind == 'acceptGenerated':
                proposal_id=request.get('proposalId')
                if not isinstance(proposal_id,str):
                    raise DomainError('INVALID','생성 제안을 확인해 주세요.')
                row=db.execute('SELECT * FROM generated_proposals WHERE id=?',(proposal_id,)).fetchone()
                if row is None:
                    raise DomainError('NOT_FOUND','생성 제안을 다시 찾아 주세요.',404)
                if row['accepted_id']:
                    body=self._version(db,row['accepted_id'],1)
                    result={'routine':body,'libraryRevision':db.execute("SELECT value FROM metadata WHERE key='library_revision'").fetchone()[0]}
                    db.execute('INSERT INTO commands VALUES(?,?,?)',(request['commandId'],digest,json.dumps(result,ensure_ascii=False)))
                    return result
                if time.time()-row['created']>86400:
                    raise DomainError('PROPOSAL_EXPIRED','생성 제안을 다시 찾아 주세요.',409)
                original=json.loads(row['body']);did=uid()
                body=dict(validate_content(original),id=did,version=1,source='collected',
                          author=original['author'],origin=None,createdAt=now(),
                          generation={'provider':'meta','model':'muse-spark-1.3','proposalId':proposal_id})
                db.execute('UPDATE generated_proposals SET accepted_id=? WHERE id=?',(did,proposal_id))
            elif kind == 'collectRoutine':
                original = next((r for r in CATALOG if r['id'] == request.get('sourceId') and r['version'] == request.get('sourceVersion')), None)
                if original is None:
                    raise DomainError('NOT_FOUND', '추가할 원본을 찾을 수 없습니다.', 404)
                existing = [json.loads(r[0]) for r in db.execute('SELECT v.body FROM definitions d JOIN versions v ON d.id=v.definition_id AND d.current_version=v.version')]
                body = next((r for r in existing if r.get('origin',{} ) and r['origin']['id'] == original['id'] and r['origin']['version'] == original['version']), None)
                if body is None:
                    body = dict(validate_content(original),id=uid(),version=1,author=original['author'],source='collected',createdAt=now(),origin={'id':original['id'],'version':original['version'],'author':original['author'],'title':original['title']})
                else:
                    result = {'routine':body,'libraryRevision':db.execute("SELECT value FROM metadata WHERE key='library_revision'").fetchone()[0]}
                    db.execute('INSERT INTO commands VALUES(?,?,?)',(request['commandId'],digest,json.dumps(result,ensure_ascii=False)))
                    return result
                did = body['id']
            else:
                raise DomainError('INVALID', '지원하지 않는 저장 동작입니다.')
            db.execute('INSERT INTO versions VALUES(?,?,?)',(did,body['version'],json.dumps(body,ensure_ascii=False)))
            db.execute('INSERT OR REPLACE INTO definitions VALUES(?,?)',(did,body['version']))
            db.execute("UPDATE metadata SET value=value+1 WHERE key='library_revision'")
            result={'routine':body,'libraryRevision':db.execute("SELECT value FROM metadata WHERE key='library_revision'").fetchone()[0]}
            db.execute('INSERT INTO commands VALUES(?,?,?)',(request['commandId'],digest,json.dumps(result,ensure_ascii=False)))
            return result
