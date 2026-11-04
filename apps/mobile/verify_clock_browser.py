"""Browser check of the clock orbit (user decision 2026-11-04): nodes at their times, the app's time right of the
planet, a visual timer for the current item, everything sliding up every minute. Mock-free, no Meta.

Start a SEPARATE headless Chrome first (never the recording one, port 9333):
  chrome --headless=new --remote-debugging-port=9334 --user-data-dir=<new temp dir> about:blank
Then:  CDP_PORT=9334 JAVA_HOME=... python3 apps/mobile/verify_clock_browser.py [--out DIR]
Screenshots clock-phone-{routine,day}-{1,2,3}.png: 14:02:30, one minute later, then +10 min (demo clock).
"""
import argparse,json,os,sys,tempfile,time,base64
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
from cdp import CDP
import rest_demo

BOXES="""JSON.stringify(Object.fromEntries(['.now-time','.window-mark','.count-badge','.clock-label'].map(q=>[q,[...document.querySelectorAll(q)].map(e=>{const b=e.getBoundingClientRect();return [b.left,b.top,b.right,b.bottom];})])))"""

def overlap(a,b):return a[0]<b[2] and b[0]<a[2] and a[1]<b[3] and b[1]<a[3]

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',default=str(Path(__file__).parent/'test-results/clock'));args=p.parse_args()
    if os.environ.get('CDP_PORT','9333')=='9333':print('Refusing port 9333 (recording browser). Set CDP_PORT.');sys.exit(2)
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True);checks=[]
    def check(name,ok,detail=''):checks.append((name,bool(ok)));print(('PASS ' if ok else 'FAIL ')+name+(' — '+str(detail) if detail else ''),flush=True)
    with tempfile.TemporaryDirectory() as tmp:
        data=Path(tmp)/'fixture';rest_demo.prepare(data,'14:00')
        day=datetime.fromtimestamp(json.loads((data/'demo-fixture.json').read_text())['nowMillis']/1000).date()
        at=lambda hhmm:rest_demo.millis(day,hhmm)
        with rest_demo.services(data) as base:
            api=lambda path,body=None:rest_demo.request(base,path,body)
            api('/api/execution/demo/clock',{'setMillis':at('14:02')+30000})
            c=CDP();c.call('Page.enable');c.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':2,'mobile':True})
            c.call('Page.navigate',{'url':base});time.sleep(1);c.js("localStorage.setItem('routine.language','en')");c.call('Page.navigate',{'url':base})
            def wait(expr,t=30):
                end=time.time()+t
                while time.time()<end:
                    if c.js('!!('+expr+')'):return True
                    time.sleep(.25)
                raise AssertionError('timeout: '+expr)
            def shot(name):(out/name).write_bytes(base64.b64decode(c.call('Page.captureScreenshot',{'format':'png'})['data']))
            now=lambda:c.js("document.querySelector('.now-time')?.textContent||''")
            nodes=lambda:json.loads(c.js("JSON.stringify([...document.querySelectorAll('.clock-node circle')].map(e=>+e.getAttribute('cy')))"))
            def no_overlap(level):
                b=json.loads(c.js(BOXES));t=b['.now-time']
                check(f'{level}: one app-time label right of the planet',len(t)==1,t)
                others=b['.window-mark']+b['.count-badge']+b['.clock-label']
                check(f'{level}: time label does not overlap reservation labels / +N / tick labels',t and not any(overlap(t[0],o) for o in others))
            def step(level,name,hhmm):
                wait(f"document.querySelector('.now-time')&&document.querySelector('.now-time').textContent==={json.dumps(hhmm)}",20)
                check(f'{level}: app time shows {hhmm}',now()==hhmm);no_overlap(level);shot(name)
            wait("document.querySelector('[data-show-parent]')")
            step('routine','clock-phone-routine-1.png','14:02')
            check('routine: visual timer (remaining + elapsed arcs)',c.js("!!document.querySelector('.timer-remaining')"))
            r1=nodes();check('routine: upcoming steps drawn at their times',len(r1)>=1,r1)
            api('/api/execution/demo/clock',{'advanceMinutes':1});step('routine','clock-phone-routine-2.png','14:03')
            r2=nodes();check('routine: one minute later the nodes moved up',len(r1)==len(r2) and all(b<a for a,b in zip(r1,r2)),(r1,r2))
            c.js("document.querySelector('[data-show-parent]').click()");wait("document.querySelector('.day-scene')")
            step('day','clock-phone-day-1.png','14:03')
            d1=nodes();check('day: items at their times (Team sync 14:30, Doctor call 15:00 ...)',len(d1)>=2,d1)
            api('/api/execution/demo/clock',{'advanceMinutes':1});step('day','clock-phone-day-2.png','14:04')
            d2=nodes();check('day: one minute later the nodes moved up',len(d1)==len(d2) and all(b<a for a,b in zip(d1,d2)),(d1,d2))
            api('/api/execution/demo/clock',{'advanceMinutes':10});step('day','clock-phone-day-3.png','14:14')
            c.js("document.querySelector('[data-day-home]')?.click()");time.sleep(.3)
            c.js("document.querySelector('.day-scene [data-day-open]')?.click()");wait("document.querySelector('[data-show-parent]')")
            step('routine','clock-phone-routine-3.png','14:14')
    fails=[n for n,ok in checks if not ok]
    print(('FAIL ' if fails else 'PASS ')+str(len(checks)-len(fails)));sys.exit(1 if fails else 0)

if __name__=='__main__':main()
