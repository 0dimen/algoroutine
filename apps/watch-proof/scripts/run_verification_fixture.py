"""Isolated native-watch verification. Never touches ports 8780/8791 or their data.
8793: loopback proxy + fault controls; 8795: real KMP; 8784: disposable library.
Reset only the two execution files inside this process's freshly created temp root.
"""
import json,os,sys,tempfile,threading,time,uuid,subprocess
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.request import Request,urlopen
from urllib.error import HTTPError
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'mobile'))
from server import make_server
root=Path(tempfile.mkdtemp(prefix='algoroutine-watch-verification-'))
execution=root/'execution';execution.mkdir()
mobile=make_server(root/'library.sqlite3',8784,execution_url='http://127.0.0.1:8795')
threading.Thread(target=mobile.serve_forever,daemon=True).start()
env=os.environ.copy();env['JAVA_HOME']=subprocess.check_output(['/usr/libexec/java_home','-v','17'],text=True).strip()
log=(root/'kmp.log').open('w')
engine=subprocess.Popen([str(ROOT/'watch-proof/executionServer/build/install/executionServer/bin/executionServer'),'8795',str(execution),'http://127.0.0.1:8784'],env=env,stdout=log,stderr=log)
def call(path,body=None):
 req=Request('http://127.0.0.1:8795'+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json','X-Routine-App':'local'})
 with urlopen(req,timeout=10) as response:return json.load(response)
for _ in range(60):
 try:call('/context');break
 except Exception:time.sleep(.25)
else:raise RuntimeError('Fixture engine did not start')
def create(title,steps,description='Prepared verification routine.'):
 return mobile.store.command({'commandId':str(uuid.uuid4()),'kind':'saveDefinition','content':{'title':title,'description':description,'steps':[{'id':chr(97+i),'title':v} for i,v in enumerate(steps)]}})['routine']
a=create('Report draft',['Open document','Write heading','List key points'],'Original report instructions.')
b=create('Reset focus',['Take one breath','Choose next action'],'Pause and choose a concrete next action.')
n=create('Next reservation',['Prepare notes'])
k=create('보고서 초안을 시작하기 전에 필요한 자료와 핵심 내용을 정리하는 작업',['보고서 초안을 시작하기 위해 새 문서를 열고 첫 문장을 준비하기','핵심 내용을 차근차근 정리하기'])
mode='normal';lock=threading.RLock();last={}
def command(kind,occ,**extra):
 w=call('/context')['workspace'];run=next((r for r in w['runs'] if r['id']==occ),None)
 c={'id':str(uuid.uuid4()),'kind':kind,'occurrenceId':occ,'expectedRevision':run['revision'] if kind in ('complete','defer','skip','completeParent') else w['revision']}
 if kind in ('complete','defer','skip'):c.update(unitId=run['currentUnitId'],expectedFocusRevision=w['focusRevision'])
 if kind=='completeParent':c['expectedFocusRevision']=w['focusRevision']
 c.update(extra);out=call('/command',c);assert out['result']['accepted'],out;return out

def start(r,occ):return command('start',occ,definition={'id':r['id'],'version':r['version'],'title':r['title'],'author':'','steps':[]})
def reserve(r,key,start_ms,end_ms):return call('/reservations',{'id':key,'definitionId':r['id'],'definitionVersion':r['version'],'title':r['title'],'startMillis':start_ms,'endMillis':end_ms})
def reset(name):
 global mode,last
 mode='normal'
 for file in ['workspace-v2.json','reservations-v1.json']:
  p=execution/file
  if p.exists():p.unlink()
 now=int(time.time()*1000)
 if name=='concurrent':
  start(a,'original');command('complete','original');start(b,'other');command('focus','original')
 elif name in ('active','gesture'):
  start(a,'original')
 elif name=='long-ko':start(k,'long')
 elif name=='conflict':
  reserve(a,'choice-a',now-1000,now+600000);reserve(b,'choice-b',now-1000,now+600000)
 elif name=='timed':
  reserve(b,'short',now-20000,now+40000);reserve(n,'next',now+40000,now+600000);start(b,'reserved-short')
 elif name=='future':reserve(n,'future',now+600000,now+900000)
 elif name!='empty':raise ValueError('Unknown scenario')
 last={'scenario':name,'context':call('/context'),'root':str(root)}
 (root/'last-scenario.json').write_text(json.dumps(last,ensure_ascii=False,indent=2))
 return last
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def send(self,status,data):
  raw=json.dumps(data,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
 def do_GET(self):self.handle_it()
 def do_POST(self):self.handle_it()
 def handle_it(self):
  global mode
  try:
   assert self.headers.get('Host') in ['127.0.0.1:8793','localhost:8793','10.0.2.2:8793']
   body=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0')))) if self.command=='POST' else None
   with lock:
    if self.path=='/__reset':out=reset(body['scenario']);self.send(200,out);return
    if self.path=='/__mode':mode=body['mode'];assert mode in ['normal','read_error','search_error','drop_command_once'];self.send(200,{'mode':mode});return
    if self.path=='/__state':self.send(200,{'mode':mode,'root':str(root),'context':call('/context')});return
    assert self.path in ['/context','command','/command','/search','/events','/reservations']
    if mode=='read_error' and self.path=='/context' or mode=='search_error' and self.path=='/search':self.send(503,{'error':'injected_read_error'});return
    out=call(self.path,body)
    if mode=='drop_command_once' and self.path=='/command':mode='normal';self.send(503,{'error':'injected_response_loss'});return
    self.send(200,out)
  except HTTPError as e:self.send(e.code,{'error':'upstream'})
  except Exception as e:self.send(500,{'error':str(e)})
proxy=ThreadingHTTPServer(('127.0.0.1',8793),Handler)
print(json.dumps({'verification':'http://127.0.0.1:8793','root':str(root)},ensure_ascii=False),flush=True)
try:proxy.serve_forever()
finally:proxy.server_close();mobile.shutdown();engine.terminate();engine.wait(timeout=10);log.close()
