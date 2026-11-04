import json,os,socket,subprocess,sys,tempfile,threading,time,unittest
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'apps/mobile'))
from server import make_server
class IntegrationFixture(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.base=Path(cls.tmp.name)
  sock=socket.socket();sock.bind(('127.0.0.1',0));cls.port=sock.getsockname()[1];sock.close()
  cls.mobile=make_server(cls.base/'library.db',0,f'http://127.0.0.1:{cls.port}');threading.Thread(target=cls.mobile.serve_forever,daemon=True).start();cls.url=f'http://127.0.0.1:{cls.mobile.server_port}'
  cls.launch()
 @classmethod
 def launch(cls):
  env=os.environ.copy()
  if 'JAVA_HOME' not in env and Path('/usr/libexec/java_home').exists():
   env['JAVA_HOME']=subprocess.check_output(['/usr/libexec/java_home','-v','17'],text=True).strip()
  cls.proc=subprocess.Popen([str(ROOT/'apps/watch-proof/executionServer/build/install/executionServer/bin/executionServer'),str(cls.port),str(cls.base/'execution'),cls.url],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  for _ in range(80):
   try:
    with urlopen(f'http://127.0.0.1:{cls.port}/context',timeout=1):return
   except OSError:time.sleep(.1)
  raise RuntimeError('server did not start')
 @classmethod
 def tearDownClass(cls):
  cls.proc.terminate();cls.proc.wait(timeout=10);cls.mobile.shutdown();cls.mobile.server_close();cls.tmp.cleanup()
 def call(self,path,body=None):
  req=Request(self.url+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json','X-Routine-App':'local'})
  with urlopen(req,timeout=8) as r:return json.load(r)
class Integration(IntegrationFixture):
 def test_full_flow(self):
  routine=self.call('/api/commands',{'commandId':'create','kind':'saveDefinition','content':{'title':'보고서 초안 시작','steps':[{'id':'a','title':'문서 열기'},{'id':'b','title':'가제 적기'},{'id':'c','title':'키워드 적기'}]}})['routine']
  collected=self.call('/api/commands',{'commandId':'collect-find','kind':'collectRoutine','sourceId':'report-start','sourceVersion':1})['routine']
  self.call('/api/drafts',{'key':'find-draft','expectedRevision':0,'content':{'title':'not a search candidate'}})
  snapshot=self.call('/api/execution/context')['workspace']
  with urlopen(f'http://127.0.0.1:{self.port}/library') as response:found=json.load(response)['items']
  self.assertEqual({r['id'] for r in found},{routine['id'],collected['id']})
  self.assertEqual(next(r for r in found if r['id']==collected['id'])['author']['name'],'루틴 스튜디오')
  self.assertEqual(self.call('/api/execution/context')['workspace'],snapshot)
  d={'id':routine['id'],'version':routine['version'],'title':'untrusted client title','author':'wrong','steps':[]}
  def context():return self.call('/api/execution/context')
  def send(c):return self.call('/api/execution/command',c)
  def start(key):return send({'id':'start-'+key,'kind':'start','occurrenceId':key,'expectedRevision':context()['workspace']['revision'],'definition':d})
  def act(kind,key):
   w=context()['workspace'];r=next(x for x in w['runs'] if x['id']==w['focusId'])
   return send({'id':key,'kind':kind,'occurrenceId':r['id'],'expectedRevision':r['revision'],'unitId':None if kind=='completeParent' else r['currentUnitId'],'expectedFocusRevision':w['focusRevision']})
  first=start('one');self.assertTrue(first['result']['accepted']);self.assertEqual(first['context']['workspace']['runs'][0]['definition']['title'],routine['title'])
  out=act('defer','defer');self.assertEqual(out['context']['workspace']['runs'][0]['currentUnitId'],'b')
  act('complete','complete-b');self.assertEqual(context()['workspace']['runs'][0]['currentUnitId'],'a')
  start('two');w=context()['workspace'];send({'id':'focus-one','kind':'focus','occurrenceId':'one','expectedRevision':w['revision']})
  self.assertEqual(context()['workspace']['runs'][0]['currentUnitId'],'a')
  act('skip','skip-a');act('complete','complete-c');r=context()['workspace']['runs'][0];self.assertEqual(r['status'],'exhausted');self.assertIsNone(r['evidence'])
  act('completeParent','parent');self.assertEqual(context()['workspace']['runs'][0]['evidence'],'direct_parent')
  # Historical response receipt, but fresh context; replay does not refetch unavailable definitions.
  retry={'id':'start-one','kind':'start','occurrenceId':'one','expectedRevision':0,'definition':d}
  before=context()['workspace'];again=send(retry);self.assertEqual(before,again['context']['workspace']);self.assertEqual(again['result'],first['result'])
  # A lost response can be recovered even while the definition lookup is unavailable.
  original_version=self.mobile.store.version
  def unavailable(*args,**kwargs):
   from store import DomainError
   raise DomainError('UNAVAILABLE','Unavailable',503)
  self.mobile.store.version=unavailable
  try:self.assertEqual(before,send(retry)['context']['workspace'])
  finally:self.mobile.store.version=original_version
  # Saved version stays frozen across later definition edits.
  self.call('/api/commands',{'commandId':'edit','kind':'saveDefinition','definitionId':routine['id'],'expectedVersion':1,'content':{'title':'변경된 이름','steps':[{'id':'a','title':'변경된 행동'}]}})
  self.assertEqual(context()['workspace']['runs'][1]['definition']['title'],'보고서 초안 시작')
  # Workspace survives complete process restart without a second start.
  self.proc.terminate();self.proc.wait(timeout=10);self.__class__.launch();self.assertEqual(before,context()['workspace'])
  now=int(time.time()*1000)
  reservation={'id':'tomorrow','definitionId':routine['id'],'definitionVersion':1,'title':'fake','startMillis':now+60000,'endMillis':now+120000}
  items=self.call('/api/execution/reservations',reservation);self.assertEqual(items[0]['title'],'보고서 초안 시작')
  c=context();self.assertEqual(c['reservation']['state'],'selected');self.assertEqual(len(c['workspace']['runs']),2)
  out=send({'id':'early','kind':'start','occurrenceId':'reserved-tomorrow','expectedRevision':c['workspace']['revision'],'definition':d});self.assertEqual(out['result']['reason'],'EARLY_START')
  # Server origin guards and proxy do not bypass the mobile origin guard.
  req=Request(self.url+'/api/execution/command',data=b'{}',headers={'Content-Type':'application/json','X-Routine-App':'local','Origin':'https://evil.example'})
  with self.assertRaises(HTTPError) as caught:urlopen(req)
  self.assertEqual(caught.exception.code,403)
class SearchIntegration(IntegrationFixture):
 def test_search_catalog_start_without_collect(self):
  before=self.call('/api/library')
  req=Request(f'http://127.0.0.1:{self.port}/search',data=json.dumps({'query':'소제목'}).encode(),headers={'Content-Type':'application/json','X-Routine-App':'local'})
  with urlopen(req) as response:result=json.load(response)
  candidate=result['items'][0];self.assertEqual(candidate['id'],'report-start')
  w=self.call('/api/execution/context')['workspace']
  cmd={'id':'catalog-start','kind':'start','occurrenceId':'catalog-search-run','expectedRevision':w['revision'],'definition':{'id':candidate['id'],'version':candidate['version'],'title':'ignored','author':'','steps':[]}}
  out=self.call('/api/execution/command',cmd);self.assertTrue(out['result']['accepted'])
  run=next(r for r in out['context']['workspace']['runs'] if r['id']=='catalog-search-run')
  self.assertEqual(run['definition']['title'],candidate['title']);self.assertEqual(run['definition']['author'],'루틴 스튜디오')
  self.assertEqual(self.call('/api/library'),before)
  self.assertEqual(self.call('/api/execution/command',cmd)['context']['workspace'],out['context']['workspace'])


class GapIntegration(IntegrationFixture):
 def test_frozen_detail_conflict_choice_and_background_expiry(self):
  import uuid
  def command(kind,**args):return self.call('/api/commands',dict(commandId=str(uuid.uuid4()),kind=kind,**args))
  a=command('saveDefinition',content={'title':'예약 A','description':'보존할 설명','steps':[{'id':'a','title':'첫 행동'},{'id':'b','title':'두 번째 행동'}]})['routine']
  b=command('saveDefinition',content={'title':'예약 B','description':'선택한 설명','steps':[{'id':'x','title':'선택한 행동'}]})['routine']
  now=int(time.time()*1000)
  for key,r in [('a',a),('b',b)]:self.call('/api/execution/reservations',{'id':key,'definitionId':r['id'],'definitionVersion':1,'title':'ignored','startMillis':now-1000,'endMillis':now+60000})
  c=self.call('/api/execution/context');self.assertEqual(c['reservation']['state'],'conflict');self.assertEqual(len(c['workspace']['runs']),0)
  self.assertEqual(c['workspace'],self.call('/api/execution/context')['workspace'])
  def start(r,occ):
   w=self.call('/api/execution/context')['workspace']
   return self.call('/api/execution/command',{'id':str(uuid.uuid4()),'kind':'start','occurrenceId':occ,'expectedRevision':w['revision'],'definition':{'id':r['id'],'version':1,'title':'fake','author':'fake','description':'fake','steps':[]}})
  out=start(b,'reserved-b');self.assertTrue(out['result']['accepted']);run=out['context']['workspace']['runs'][0]
  self.assertEqual(run['definition']['description'],'선택한 설명');self.assertEqual([x['id'] for x in out['context']['reservation']['candidates']],['a'])
  command('saveDefinition',definitionId=b['id'],expectedVersion=1,content={'title':'바꾼 제목','description':'바꾼 설명','steps':[{'id':'x','title':'바꾼 행동'}]})
  self.assertEqual(self.call('/api/execution/context')['workspace']['runs'][0],run)
  # A short reservation expires without context polling; ticker records the event durably.
  now=int(time.time()*1000);end=now+1800
  self.call('/api/execution/reservations',{'id':'short','definitionId':a['id'],'definitionVersion':1,'title':'ignored','startMillis':now-1000,'endMillis':end})
  short=start(a,'reserved-short');self.assertTrue(short['result']['accepted'])
  journal=self.base/'execution/workspace-v2.json';deadline=time.monotonic()+6
  while time.monotonic()<deadline:
   entries=json.loads(journal.read_text())['entries']
   if any(e['command']['kind']=='expire' for e in entries):break
   time.sleep(.1)
  self.assertEqual(sum(e['command']['kind']=='expire' for e in entries),1)
  c=self.call('/api/execution/context');expired=next(r for r in c['workspace']['runs'] if r['id']=='reserved-short')
  self.assertEqual(expired['status'],'elapsed');self.assertEqual(expired['completed'],0);self.assertEqual(expired['skipped'],0);self.assertTrue(all(s['status']=='elapsed' for s in expired['steps']))
  self.assertEqual(c['reservation']['candidates'][0]['id'],'a')
  late=self.call('/api/execution/command',{'id':'late-complete','kind':'complete','occurrenceId':'reserved-short','expectedRevision':0,'expectedFocusRevision':c['workspace']['focusRevision'],'unitId':'a'})
  self.assertEqual(late['result']['reason'],'WINDOW_ELAPSED');self.assertEqual(late['context']['workspace'],c['workspace'])
  self.proc.terminate();self.proc.wait(timeout=10);self.__class__.launch()
  self.assertEqual(self.call('/api/execution/context')['workspace'],c['workspace'])
  with urlopen(f'http://127.0.0.1:{self.port}/events') as response:events=json.load(response)
  self.assertEqual(sum(e['kind']=='expire' for e in events),1)
  # System expiry cannot be injected through the public local command endpoint.
  with self.assertRaises(HTTPError):self.call('/api/execution/command',{'id':'system:elapsed:reserved-b','kind':'expire','occurrenceId':'reserved-b','expectedRevision':0})

if __name__=='__main__':unittest.main()

class GeneratedIntegration(IntegrationFixture):
 def test_generated_preview_accept_start_and_complete_preserves_other_run(self):
  from recommendation_service import RecommendationService
  from test_recommendation import Fake
  content={'title':'출발 전 화분 확인','description':'흙부터 확인','steps':[{'id':'soil','title':'흙 만져 보기'},{'id':'water','title':'필요한 화분에 물 주기'}]}
  self.mobile.recommendations=RecommendationService(self.mobile.store,lambda:Fake({'status':'no_fit','choices':[]},content))
  original=self.call('/api/commands',{'commandId':'original-create','kind':'saveDefinition','content':{'title':'기존 작업','steps':[{'id':'one','title':'문서 열기'}]}})['routine']
  def context():return self.call('/api/execution/context')
  def start(r,key):return self.call('/api/execution/command',{'id':key,'kind':'start','occurrenceId':key,'expectedRevision':context()['workspace']['revision'],'definition':{'id':r['id'],'version':r['version'],'title':r['title'],'author':r['author']['name'],'steps':r['steps']}})
  self.assertTrue(start(original,'original')['result']['accepted'])
  before=context()['workspace'];original_run=before['runs'][0]
  proposal=self.call('/api/recommend',{'query':'화분 물 주기'})['items'][0]
  self.assertEqual(context()['workspace'],before)
  self.assertEqual(len(self.call('/api/library')['items']),1)
  accepted=self.call('/api/commands',{'commandId':'accept-generated','kind':'acceptGenerated','proposalId':proposal['id']})['routine']
  self.assertEqual(context()['workspace'],before)
  self.assertTrue(start(accepted,'generated')['result']['accepted'])
  for index in range(2):
   w=context()['workspace'];run=next(r for r in w['runs'] if r['id']=='generated')
   self.assertEqual(run['definition']['author'],'Meta AI')
   out=self.call('/api/execution/command',{'id':'complete-generated-'+str(index),'kind':'complete','occurrenceId':'generated','unitId':run['currentUnitId'],'expectedRevision':run['revision'],'expectedFocusRevision':w['focusRevision']})
   self.assertTrue(out['result']['accepted'])
  final=context()['workspace']
  self.assertEqual(next(r for r in final['runs'] if r['id']=='original'),original_run)
  self.assertTrue(all(s['status']=='completed' for s in next(r for r in final['runs'] if r['id']=='generated')['steps']))
