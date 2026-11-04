"""Create new test-only mobile definitions; never reset existing records.
Run with an isolated run_integrated.py --data directory. Prints fixture for UI tests.
"""
import json,time,uuid,sys
from urllib.request import Request,urlopen

def call(path,body=None):
    req=Request('http://127.0.0.1:8780'+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json','X-Routine-App':'local'})
    with urlopen(req,timeout=10) as r:return json.load(r)
def routine(title,steps):
    return call('/api/commands',{'commandId':str(uuid.uuid4()),'kind':'saveDefinition','content':{'title':title,'steps':[{'id':key,'title':name} for key,name in steps]}})['routine']
if '--use-existing' in sys.argv:
    matches=[r for r in call('/api/library')['items'] if r['title']=='통합 검증 루틴']
    assert len(matches)==1, 'Expected one UI-created fixture'
    a=matches[0]
    assert [s['title'] for s in a['steps']]==['문서 열기','가제 적기','키워드 적기']
else:
    a=routine('보고서 초안 시작' if '--active' in sys.argv else '통합 검증 루틴',[('a','문서 열기'),('b','가제 적기'),('c','키워드 적기')])
if '--with-collected' in sys.argv:
    call('/api/commands',{'commandId':str(uuid.uuid4()),'kind':'collectRoutine','sourceId':'report-start','sourceVersion':1})
if '--active' in sys.argv:
    w=call('/api/execution/context')['workspace'];occ=str(uuid.uuid4())
    out=call('/api/execution/command',{'id':str(uuid.uuid4()),'kind':'start','occurrenceId':occ,'expectedRevision':w['revision'],'definition':{'id':a['id'],'version':a['version'],'title':a['title'],'author':a['author']['name'],'steps':a['steps']}})
    assert out['result']['accepted']
    print(json.dumps({'primary':a,'occurrence':occ},ensure_ascii=False));raise SystemExit(0)
b=routine('함께 진행 검증',[('x','호흡 고르기'),('y','한 줄 정리')])
if '--search-input' in sys.argv:
    b=call('/api/commands',{'commandId':str(uuid.uuid4()),'kind':'saveDefinition','definitionId':b['id'],'expectedVersion':b['version'],'content':dict(b,description='breath')})['routine']
key=str(uuid.uuid4());now=int(time.time()*1000)
call('/api/execution/reservations',{'id':key,'definitionId':a['id'],'definitionVersion':a['version'],'title':a['title'],'startMillis':now-1000,'endMillis':now+3600000})
print(json.dumps({'primary':a,'other':b,'occurrence':'reserved-'+key},ensure_ascii=False))
