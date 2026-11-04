"""No-key browser rehearsal against a copy of prepared data; no watch/voice claim."""
import argparse,base64,json,shutil,subprocess,tempfile,time
from pathlib import Path
from urllib.request import urlopen
import websocket
from prepare_submission_demo import services,request,save

class Browser:
    def __init__(self,folder):
        self.process=subprocess.Popen(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome','--headless=new','--no-first-run','--no-default-browser-check','--remote-debugging-port=0','--user-data-dir='+str(folder),'about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        self.ws=None;self.n=0
        try:
            for _ in range(100):
                active=folder/'DevToolsActivePort'
                if active.exists():break
                if self.process.poll() is not None:raise RuntimeError('Chrome exited')
                time.sleep(.1)
            port=int(active.read_text().splitlines()[0])
            tabs=json.load(urlopen(f'http://127.0.0.1:{port}/json/list'))
            self.ws=websocket.create_connection(next(t['webSocketDebuggerUrl'] for t in tabs if t['type']=='page'),timeout=10,suppress_origin=True)
        except Exception:self.close();raise
    def close(self):
        if self.ws:self.ws.close()
        if self.process.poll() is None:
            self.process.terminate()
            try:self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait()
    def call(self,method,params=None):
        self.n+=1;self.ws.send(json.dumps({'id':self.n,'method':method,'params':params or {}}))
        while True:
            result=json.loads(self.ws.recv())
            if result.get('id')==self.n:
                if 'error' in result:raise RuntimeError(result['error']['message'])
                return result.get('result',{})
    def js(self,expression):
        result=self.call('Runtime.evaluate',{'expression':expression,'returnByValue':True,'awaitPromise':True})
        if 'exceptionDetails' in result:raise RuntimeError('Browser expression failed')
        return result['result'].get('value')
    def wait(self,expression):
        for _ in range(80):
            if self.js(expression):return
            time.sleep(.1)
        raise AssertionError(expression)
    def click(self,selector):self.js('document.querySelector('+json.dumps(selector)+').click()')
    def screenshot(self,path):path.write_bytes(base64.b64decode(self.call('Page.captureScreenshot',{'format':'png'})['data']))

def verify(data,output):
    manifest=json.loads((data/'manifest.json').read_text());output.mkdir(parents=True,exist_ok=True);checks=[]
    save(output/'results.json',{'passed':False,'status':'started','mode':'no-key browser rehearsal'})
    with tempfile.TemporaryDirectory(prefix='routine-browser-') as temp:
        folder=Path(temp);clone=folder/'data';shutil.copytree(data,clone)
        with services(clone) as (base,_):
            c=Browser(folder/'chrome')
            try:
                c.call('Page.enable');c.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
                c.call('Page.navigate',{'url':base});c.wait('document.querySelectorAll("#content [data-open]").length===6');c.click('[data-nav=current]')
                c.wait('document.querySelector("h1")?.textContent==="Write a working heading"');checks.append('initial heading displayed')
                before=request(base,'/api/execution/context')['workspace']['runs'][0];reservations=request(base,'/api/execution/reservations')
                c.click('[data-nav=find]');c.wait('!!document.querySelector("#search-input")')
                c.js('(()=>{const e=document.querySelector("#search-input");e.value="Pause and breathe";e.dispatchEvent(new Event("input",{bubbles:true}));document.querySelector("#search-form").requestSubmit()})()')
                selector='[data-open="'+manifest['mapping']['breathe']['id']+'"]'
                c.wait('!!document.querySelector('+json.dumps(selector)+')');c.click(selector)
                c.wait('document.querySelectorAll("#content li").length===3');checks.append('whole routine detail shown')
                assert request(base,'/api/execution/context')['workspace']['runs']==[before];checks.append('detail does not start')
                c.click('[data-start]');c.wait('document.querySelector("h1")?.textContent==="Put both feet on the floor"');checks.append('start shows concrete first action')
                c.screenshot(output/'first-action.png')
                for expected in ('Take a few comfortable breaths','Name one thing you can do next'):
                    c.click('[data-action=complete]');c.wait('document.querySelector("h1")?.textContent==='+json.dumps(expected));checks.append('complete advances to '+expected)
                c.click('[data-action=complete]');c.wait('document.querySelector("#content")?.textContent.includes("Sort your inbox") && !document.querySelector("[data-action=complete]")');checks.append('completion displays next reservation')
                c.screenshot(output/'next-reservation.png')
                state=request(base,'/api/execution/context')['workspace'];assert len(state['runs'])==2 and state['runs'][0]==before;checks.append('future reservation not auto-started and prior progress preserved')
                c.click('details.together summary');c.click('[data-focus="demo-report"]');c.wait('document.querySelector("h1")?.textContent==="Write a working heading"')
                state=request(base,'/api/execution/context')['workspace'];assert state['focusId']=='demo-report' and state['runs'][0]==before and len(state['runs'])==2;checks.append('return after completion preserves original occurrence')
                assert request(base,'/api/execution/reservations')==reservations;checks.append('reservation times unchanged')
                assert c.js('document.documentElement.scrollWidth<=390');checks.append('no horizontal overflow at 390px')
                c.screenshot(output/'returned-report.png')
                save(output/'results.json',{'passed':True,'checks':checks,'mode':'Chrome headless mobile viewport, real app/KMP, no-key lexical search','notVerified':['live speech','live Meta through browser','native watch UI','physical device','human action or outcome']})
            finally:c.close()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',required=True);p.add_argument('--output',required=True);a=p.parse_args();verify(Path(a.data).resolve(),Path(a.output).resolve());print('Browser rehearsal passed')
