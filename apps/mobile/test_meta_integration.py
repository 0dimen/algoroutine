import io,json,tempfile,threading,time,unittest
from pathlib import Path
from urllib.error import HTTPError,URLError
from urllib.request import Request,urlopen
from meta_provider import MetaProvider,MODEL
from recommendation_service import RecommendationService
from store import Store,DomainError
from server import make_server
from test_recommendation import Fake,DRAFT

class Opener:
 def __init__(self,value):self.value=value;self.requests=[]
 def open(self,req,timeout):
  self.requests.append((req,timeout))
  if isinstance(self.value,Exception):raise self.value
  return io.BytesIO(json.dumps(self.value).encode())

def response(value,finish='stop'):
 return {'choices':[{'finish_reason':finish,'message':{'content':json.dumps(value)}}],
         'usage':{'prompt_tokens':100,'completion_tokens':20,'total_tokens':120}}

class ProviderTests(unittest.TestCase):
 def test_official_standard_endpoint_minimal_data_and_usage(self):
  o=Opener(response({'status':'no_fit','choices':[]}));p=MetaProvider('test-secret',o)
  p.recommend('문서',[{'id':'a','version':1,'source':'mine','title':'원문','author':{'name':'비공개 이름'},'description':'설명','steps':[]}])
  req,timeout=o.requests[0];body=json.loads(req.data)
  self.assertEqual(req.full_url,'https://api.meta.ai/v1/chat/completions')
  self.assertEqual(body['model'],MODEL);self.assertNotIn('contributor',body['model'])
  self.assertNotIn('비공개 이름',req.data.decode());self.assertNotIn('test-secret',req.data.decode())
  self.assertEqual(p.metrics[0]['total_tokens'],120);self.assertNotIn('content',p.metrics[0])
 def test_errors_and_timeouts_are_safe_without_retry(self):
  for exc in (HTTPError('https://api.meta.ai',401,'secret response',{},None),TimeoutError()):
   o=Opener(exc);p=MetaProvider('secret-key',o)
   with self.assertRaises(DomainError) as caught:p.generate('문서')
   self.assertNotIn('secret',str(caught.exception));self.assertEqual(len(o.requests),1)
 def test_header_and_body_timeouts_are_classified_without_retry(self):
  class BodyTimeout:
   def __enter__(self):return self
   def __exit__(self,*args):self.closed=True
   def read(self,*args):raise TimeoutError('private diagnostic')
  class BodyOpener(Opener):
   def open(self,req,timeout):self.requests.append((req,timeout));return self.value
  body=BodyTimeout()
  cases=[(Opener(URLError(TimeoutError('private diagnostic'))),'META_TIMEOUT','awaiting_headers'),
         (BodyOpener(body),'META_TIMEOUT','reading_body'),
         (Opener(URLError(ConnectionRefusedError('private diagnostic'))),'META_UNAVAILABLE','awaiting_headers')]
  for opener,code,phase in cases:
   with self.subTest(code=code,phase=phase):
    provider=MetaProvider('synthetic-key',opener)
    with self.assertRaises(DomainError) as caught:provider.generate('synthetic input')
    self.assertEqual(caught.exception.code,code);self.assertEqual(len(opener.requests),1)
    self.assertEqual(provider.metrics[0]['phase'],phase)
    self.assertNotIn('private',json.dumps(provider.metrics)+str(caught.exception))
  self.assertTrue(body.closed)

 def test_truncation_and_malformed_content_rejected(self):
  for value in (response({},'length'),{'choices':[]},response('not an object')):
   o=Opener(value);p=MetaProvider('key',o)
   if value==response('not an object'):
    # The boundary validator, not transport, validates parsed schema.
    self.assertEqual(p.generate('문서'),'not an object')
   else:
    with self.assertRaises(DomainError):p.generate('문서')
 def test_wrong_typed_provider_envelopes_are_safe_errors(self):
  valid=response({'status':'no_fit','choices':[]})
  cases=[[],None,dict(valid,usage=[]),dict(valid,choices='x'),
         dict(valid,choices=[None]),dict(valid,choices=[{'finish_reason':'stop','message':[]}])]
  for value in cases:
   with self.subTest(value=value):
    opener=Opener(value);provider=MetaProvider('synthetic-key',opener)
    with self.assertRaises(DomainError) as e:provider.recommend('문서',[])
    self.assertEqual(e.exception.code,'META_INVALID')
    self.assertEqual(len(opener.requests),1)
    self.assertEqual(provider.metrics[0]['status'],'error')


class LiveCheckBudgetTests(unittest.TestCase):
 def test_live_check_never_exceeds_total_call_budget(self):
  from verify_meta_live import BudgetedProvider
  fake=Fake();fake.metrics=[];budget=[4];providers=[BudgetedProvider(fake,budget),BudgetedProvider(fake,budget)]
  for i in range(4):providers[i%2].generate('synthetic')
  with self.assertRaises(DomainError) as caught:providers[0].recommend('synthetic',[])
  self.assertEqual(caught.exception.code,'LIVE_CHECK_BUDGET');self.assertEqual(len(fake.calls),4)

class ResponseDeliveryTests(unittest.TestCase):
 def test_cancelled_response_does_not_retry_or_hide_other_errors(self):
  from server import Handler
  class Writer:
   def __init__(self,error):self.error=error;self.calls=0
   def write(self,raw):self.calls+=1;raise self.error
  for error in [BrokenPipeError(),ConnectionResetError(),OSError('other IO error')]:
   h=object.__new__(Handler);h.headers={};h.send_response=lambda *a:None;h.send_header=lambda *a:None;h.end_headers=lambda:None;h.wfile=Writer(error)
   if type(error) is OSError:
    with self.assertRaises(OSError):h.respond(200,{'ok':True})
   else:
    h.respond(200,{'ok':True});self.assertTrue(h.close_connection)
   self.assertEqual(h.wfile.calls,1)


class IntegrationTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'db')
 def tearDown(self):self.tmp.cleanup()
 def service(self,p=None):return RecommendationService(self.store,lambda:p or Fake({'status':'no_fit','choices':[]}))
 def test_preview_excluded_and_acceptance_idempotent_after_restart(self):
  result=self.service().recommend('문서');item=result['items'][0]
  self.assertEqual(self.store.library()['items'],[])
  request={'commandId':'accept','kind':'acceptGenerated','proposalId':item['id']}
  first=self.store.command(request);self.assertEqual(first['routine']['author']['name'],'Meta AI')
  self.assertEqual(first['routine']['source'],'collected')
  reopened=Store(self.store.path);self.assertEqual(reopened.command(request),first)
  self.assertEqual(reopened.command(dict(request,commandId='different')),first)
  self.assertEqual(len(reopened.library()['items']),1)
  with self.assertRaises(DomainError):reopened.command(dict(request,proposalId='wrong'))
 def test_generated_edit_preserves_author_and_old_version(self):
  item=self.service().recommend('문서')['items'][0]
  first=self.store.command({'commandId':'a','kind':'acceptGenerated','proposalId':item['id']})['routine']
  second=self.store.command({'commandId':'b','kind':'saveDefinition','definitionId':first['id'],'expectedVersion':1,'content':dict(DRAFT,title='내가 수정한 제목')})['routine']
  self.assertEqual(second['author'],first['author']);self.assertEqual(self.store.version(first['id'],1),first)
 def test_query_error_no_proposal_or_library_write(self):
  with self.assertRaises(DomainError):self.service().recommend('')
  with self.store.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM generated_proposals').fetchone()[0],0)
 def test_old_snapshot_rejected(self):
  store=self.store
  class Changing(Fake):
   def recommend(self,*args):
    self.calls.append('recommend')
    store.command({'commandId':'change','kind':'saveDefinition','content':DRAFT})
    return {'status':'no_fit','choices':[]}
  provider=Changing()
  with self.assertRaises(DomainError) as e:self.service(provider).recommend('문서')
  self.assertEqual(provider.calls,['recommend'])
  self.assertEqual(e.exception.code,'SEARCH_STALE')
  with store.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM generated_proposals').fetchone()[0],0)
 def test_busy_rejects_second_request_without_calling_provider(self):
  service=self.service();service.lock.acquire()
  try:
   with self.assertRaises(DomainError) as e:service.recommend('문서')
   self.assertEqual(e.exception.code,'RECOMMENDATION_BUSY')
  finally:service.lock.release()
 def test_overlapping_requests_call_provider_once_and_release_after_failure(self):
  import concurrent.futures
  entered=threading.Event();release=threading.Event()
  class Waiting(Fake):
   def recommend(self,*args):
    self.calls.append('recommend');entered.set()
    if not release.wait(3):raise AssertionError('fixture did not release')
    raise DomainError('META_UNAVAILABLE','synthetic timeout',503)
  provider=Waiting();service=self.service(provider)
  with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
   first=pool.submit(service.recommend,'문서')
   try:
    self.assertTrue(entered.wait(2))
    with self.assertRaises(DomainError) as e:service.recommend('다른 문서')
    self.assertEqual(e.exception.code,'RECOMMENDATION_BUSY')
    self.assertEqual(provider.calls,['recommend'])
   finally:release.set()
   with self.assertRaises(DomainError):first.result(timeout=3)
  service.provider_factory=lambda:Fake({'status':'no_fit','choices':[]})
  self.assertEqual(len(service.recommend('다시 찾기')['items']),1)

 def test_change_during_generation_rejects_result_without_proposal(self):
  store=self.store
  class Changing(Fake):
   def generate(self,*args):
    store.command({'commandId':'generation-change','kind':'saveDefinition','content':DRAFT})
    return super().generate(*args)
  provider=Changing({'status':'no_fit','choices':[]})
  with self.assertRaises(DomainError) as e:self.service(provider).recommend('문서')
  self.assertEqual(e.exception.code,'SEARCH_STALE')
  self.assertEqual(provider.calls,['recommend','generate'])
  with store.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM generated_proposals').fetchone()[0],0)

 def test_expired_or_forged_proposal_rejected(self):
  item=self.service().recommend('문서')['items'][0]
  with self.store.connect() as db:db.execute('UPDATE generated_proposals SET created=?',(time.time()-86401,))
  for pid in (item['id'],'forged'):
   with self.assertRaises(DomainError):self.store.command({'commandId':pid,'kind':'acceptGenerated','proposalId':pid})
  self.assertEqual(self.store.library()['items'],[])
 def test_usage_log_omits_query_content_and_key(self):
  p=Fake({'status':'no_fit','choices':[]});p.metrics=[{'stage':'generate','model':MODEL,'prompt_tokens':12,'completion_tokens':6}]
  service=self.service(p);service.recommend('개인 요청문은 기록하지 않는다')
  audit=Path(self.store.path+'.meta-usage.jsonl')
  raw=audit.read_text();self.assertNotIn('개인 요청문',raw);self.assertNotIn(DRAFT['title'],raw)
  self.assertEqual(audit.stat().st_mode & 0o777,0o600)
  self.assertEqual(json.loads(raw)['calls'],p.metrics);self.assertFalse(service.audit_error)
 def test_http_opt_in_and_acceptance(self):
  server=make_server(Path(self.tmp.name)/'http',0,provider_factory=lambda:Fake({'status':'no_fit','choices':[]}))
  threading.Thread(target=server.serve_forever,daemon=True).start()
  def call(path,body=None,origin=None):
   h={'Content-Type':'application/json','X-Routine-App':'local'}
   if origin:h['Origin']=origin
   req=Request('http://127.0.0.1:'+str(server.server_port)+path,data=json.dumps(body).encode() if body else None,headers=h)
   with urlopen(req) as r:return json.load(r)
  try:
   self.assertTrue(call('/api/capabilities')['meta'])
   with self.assertRaises(HTTPError) as e:call('/api/recommend',{'query':'문서'},'https://evil.example')
   self.assertEqual(e.exception.code,403)
   result=call('/api/recommend',{'query':'문서'})
   self.assertEqual(call('/api/library')['items'],[])
   saved=call('/api/commands',{'commandId':'http-accept','kind':'acceptGenerated','proposalId':result['items'][0]['id']})
   self.assertEqual(saved['routine']['title'],DRAFT['title'])
   server.recommendations=None
   with self.assertRaises(HTTPError) as e:call('/api/recommend',{'query':'문서'})
   self.assertEqual(e.exception.code,503)
  finally:server.shutdown();server.server_close()

if __name__=='__main__':unittest.main()
