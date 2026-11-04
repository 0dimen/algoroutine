"""Isolated fixture only: pass --data matching a fresh run_integrated --data directory.
It models an accepted AI proposal and starts it through the mobile HTTP route.
No claim of speech recognition in this watch-only fixture.
"""
import argparse,json,sys,time
from pathlib import Path
from urllib.request import Request,urlopen
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'apps/mobile'))
from store import Store
p=argparse.ArgumentParser();p.add_argument('--data',required=True);a=p.parse_args()
data=Path(a.data).resolve()
if not str(data).startswith('/private/tmp/') and not str(data).startswith('/tmp/'):
 raise SystemExit('Use a fresh /tmp test directory, never user data')
def call(path,body=None):
 req=Request('http://127.0.0.1:8780/api/'+path,data=json.dumps(body).encode() if body else None,headers={'Content-Type':'application/json','X-Routine-App':'local'})
 with urlopen(req,timeout=8) as r:return json.load(r)
assert call('execution/context')['workspace']['runs']==[], 'Fresh fixture required'
def start(r,key):
 w=call('execution/context')['workspace']
 out=call('execution/command',{'id':key,'kind':'start','occurrenceId':key,'expectedRevision':w['revision'],'definition':{'id':r['id'],'version':r['version'],'title':r['title'],'author':r['author']['name'],'steps':r['steps']}})
 assert out['result']['accepted']
old=call('commands',{'commandId':'voice-original-create','kind':'saveDefinition','content':{'title':'기존 진행 루틴','steps':[{'id':'old','title':'기존 행동'}]}})['routine'];start(old,'voice-original')
proposal=Store(data/'library.sqlite3').propose_generated({'title':'음성으로 시작한 루틴','description':'워치 연결 합성 검증','steps':[{'id':'first','title':'모바일 첫 행동'},{'id':'second','title':'모바일 다음 행동'}]})
r=call('commands',{'commandId':'voice-accept','kind':'acceptGenerated','proposalId':proposal['id']})['routine'];start(r,'voice-generated')
now=int(time.time()*1000)
nxt=call('commands',{'commandId':'voice-next-create','kind':'saveDefinition','content':{'title':'다음 예약','steps':[{'id':'next','title':'다음 예약 행동'}]}})['routine']
call('execution/reservations',{'id':'voice-next','title':'다음 예약','definitionId':nxt['id'],'definitionVersion':1,'startMillis':now+3600000,'endMillis':now+7200000})
print('Seeded mobile-started accepted proposal, original run and future reservation')
