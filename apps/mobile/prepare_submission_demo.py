"""Fresh, disposable recording fixture using real application APIs.
Never reset an existing directory or seed an unrelated running server.
--verify checks a COPY; --live permits one recommendation call, never generation/retry.
"""
import argparse,contextlib,hashlib,json,os,shutil,socket,subprocess,tempfile,threading,time,uuid
from pathlib import Path
from urllib.request import Request,urlopen
from server import make_server
from meta_provider import MetaProvider
from store import DomainError

ROOT=Path(__file__).resolve().parents[2]
QUERY='Everything feels too much right now. I need a moment to settle down.'
class SelectionOnlyProvider(MetaProvider):
    remaining=1
    def recommend(self,*args):
        if self.remaining<=0:raise DomainError('DEMO_BUDGET','One-call rehearsal budget exhausted',429)
        self.remaining-=1
        return super().recommend(*args)
    def generate(self,*args):raise DomainError('DEMO_NO_FIT','Rehearsal expected an existing routine; generation disabled',409)

def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def request(base,path,body=None):
    req=Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json','X-Routine-App':'local'})
    with urlopen(req,timeout=25) as response:return json.load(response)

@contextlib.contextmanager
def services(data,provider=None):
    binary=ROOT/'apps/watch-proof/executionServer/build/install/executionServer/bin/executionServer'
    if not binary.is_file():raise RuntimeError('Build :executionServer:installDist first')
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    mobile=make_server(data/'library.sqlite3',0,f'http://127.0.0.1:{port}',provider_factory=(lambda:provider) if provider else None)
    thread=threading.Thread(target=mobile.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{mobile.server_port}';env=os.environ.copy();proc=None
    try:
        if not env.get('JAVA_HOME'):env['JAVA_HOME']=subprocess.check_output(['/usr/libexec/java_home','-v','17'],text=True).strip()
        proc=subprocess.Popen([str(binary),str(port),str(data/'execution'),base],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for _ in range(100):
            if proc.poll() is not None:raise RuntimeError('Execution server exited')
            try:request(base,'/api/execution/context');break
            except OSError:time.sleep(.1)
        else:raise RuntimeError('Execution server readiness timeout')
        yield base,mobile
    finally:
        if proc and proc.poll() is None:
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
        mobile.shutdown();mobile.server_close();thread.join(timeout=3)

def command(base,value):
    result=request(base,'/api/execution/command',value)
    if not result['result']['accepted']:raise RuntimeError('Command rejected: '+result['result']['reason'])
    return result

def start(base,routine,occurrence):
    w=request(base,'/api/execution/context')['workspace']
    return command(base,{'id':str(uuid.uuid4()),'kind':'start','occurrenceId':occurrence,'expectedRevision':w['revision'],'definition':{'id':routine['id'],'version':routine['version'],'title':routine['title'],'author':routine['author']['name'],'steps':routine['steps']}})

def complete(base):
    w=request(base,'/api/execution/context')['workspace'];r=next(r for r in w['runs'] if r['id']==w['focusId'])
    payload={'id':str(uuid.uuid4()),'kind':'complete','occurrenceId':r['id'],'expectedRevision':r['revision'],'unitId':r['currentUnitId'],'expectedFocusRevision':w['focusRevision']}
    return payload,command(base,payload)

def prepare(data):
    data=Path(data).resolve()
    if not any(root in data.parents for root in {Path(tempfile.gettempdir()).resolve(),Path('/tmp').resolve()}):raise ValueError('Use a NEW directory under the system temporary directory')
    data.mkdir(mode=0o700,parents=False,exist_ok=False)
    spec=json.loads((ROOT/'apps/mobile/evaluation/search_cases.json').read_text());mapping={}
    with services(data) as (base,_):
        # Use normal Save. IDs, authors and source types are real app output, not forged benchmark rows.
        for candidate in spec['candidates']:
            content={key:candidate[key] for key in ('title','description','steps')}
            mapping[candidate['id']]=request(base,'/api/commands',{'commandId':str(uuid.uuid4()),'kind':'saveDefinition','content':content})['routine']
        start(base,mapping['report-mine'],'demo-report');complete(base)
        now=int(time.time()*1000);nxt=mapping['inbox']
        reservation={'id':'demo-next','definitionId':nxt['id'],'definitionVersion':nxt['version'],'title':nxt['title'],'startMillis':now+3600000,'endMillis':now+5400000}
        request(base,'/api/execution/reservations',reservation)
        context=request(base,'/api/execution/context');candidates=request(base,'/api/search',{'query':''})['items']
        manifest={'fixture':'submission-recording-v1','createdAtMillis':now,'query':QUERY,'mapping':mapping,'candidateCount':len(candidates),'candidateSnapshot':candidates,'initialContext':context,'reservations':request(base,'/api/execution/reservations'),'scope':'Six English routines saved normally as mine, plus unchanged built-in Korean catalog. NOT the original six-candidate benchmark. Preparation completions are staged state, not human activity evidence.'}
        save(data/'manifest.json',manifest)
    return manifest

def verify(data,live=False):
    manifest=json.loads((data/'manifest.json').read_text());evidence={'mode':'live Meta selection + HTTP/KMP actions' if live else 'local lexical lookup + HTTP/KMP actions','humanSpeech':False,'physicalWatch':False,'checks':[]}
    def check(name,ok):
        evidence['checks'].append({'name':name,'passed':bool(ok)})
        if not ok:raise AssertionError(name)
    with tempfile.TemporaryDirectory(prefix='routine-rehearsal-') as tmp:
        clone=Path(tmp)/'copy';shutil.copytree(data,clone)
        provider=SelectionOnlyProvider.local() if live else None
        try:
            with services(clone,provider) as (base,mobile):
                before=request(base,'/api/execution/context');reservations=request(base,'/api/execution/reservations');original=before['workspace']['runs'][0]
                check('original paused at heading',original['currentUnitId']=='b' and original['completed']==1)
                wanted=manifest['mapping']['breathe'];endpoint='/api/recommend' if live else '/api/search'
                result=request(base,endpoint,{'query':QUERY if live else 'Pause and breathe','language':'en'})
                evidence['request']=QUERY if live else 'Pause and breathe';evidence['response']=result
                check('expected routine available',any(r['id']==wanted['id'] for r in result['items']))
                check('preview starts nothing',request(base,'/api/execution/context')['workspace']==before['workspace'])
                selected=next(r for r in result['items'] if r['id']==wanted['id'])
                check('original title and all steps preserved',selected['title']==wanted['title'] and selected['steps']==wanted['steps'])
                first=start(base,selected,'demo-pause')['context'];evidence['afterStart']=first
                check('exactly one added run',len(first['workspace']['runs'])==2)
                check('first action concrete',first['workspace']['runs'][1]['steps'][0]['title']=='Put both feet on the floor')
                for _ in range(3):
                    payload,out=complete(base)
                    replay=command(base,payload)
                    check('duplicate complete preserves workspace '+payload['unitId'],replay['context']['workspace']==out['context']['workspace'])
                finished=request(base,'/api/execution/context');evidence['afterCompletion']=finished
                check('three steps completed',finished['workspace']['runs'][1]['status']=='completed' and finished['workspace']['runs'][1]['completed']==3)
                check('next reservation displayed',finished['reservation']['state']=='selected' and finished['reservation']['candidates'][0]['id']=='demo-next')
                check('reservation not started',len(finished['workspace']['runs'])==2)
                check('prior run untouched',finished['workspace']['runs'][0]==original)
                check('reservations unchanged',request(base,'/api/execution/reservations')==reservations)
                command(base,{'id':str(uuid.uuid4()),'kind':'focus','occurrenceId':'demo-report','expectedRevision':finished['workspace']['revision']})
                restored=request(base,'/api/execution/context');evidence['afterReturn']=restored
                check('explicit return after completion',restored['workspace']['focusId']=='demo-report' and restored['workspace']['runs'][0]==original)
                check('return does not restart',len(restored['workspace']['runs'])==2)
                evidence['passed']=True
        except Exception as e:
            evidence['passed']=False;evidence['failure']=getattr(e,'code',type(e).__name__)
            if isinstance(e,AssertionError):evidence['failedCheck']=str(e)
        finally:
            if provider:evidence['calls']=provider.metrics
    save(data/('live-verification.json' if live else 'local-verification.json'),evidence)
    return evidence

def main():
    p=argparse.ArgumentParser();p.add_argument('--data',required=True);p.add_argument('--verify',action='store_true');p.add_argument('--live',action='store_true');a=p.parse_args()
    if a.live and not a.verify:p.error('--live requires --verify')
    data=Path(a.data).resolve();manifest=prepare(data)
    print('Prepared isolated fixture:',data,'candidates:',manifest['candidateCount'],flush=True)
    if a.verify:
        result=verify(data,a.live);print('Verification:',result['passed'],'checks:',len(result['checks']),flush=True)
        if not result['passed']:raise SystemExit(1)
if __name__=='__main__':main()
