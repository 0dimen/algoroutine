"""Browser check of the orbit time scale by depth (shared core OrbitScales, sent as ctx.orbit). Mock-free, no Meta.

Start a SEPARATE headless Chrome first (never the recording one, port 9333):
  chromium --headless=new --remote-debugging-port=9334 --user-data-dir=<new temp dir> about:blank
Then:  CDP_PORT=9334 JAVA_HOME=... python3 apps/mobile/verify_orbit_ticks.py [--out DIR]
Checks: routine level (a routine's steps) draws 5-min clock ticks; My routine (day) draws 10-min ticks with hour
labels; moving the demo clock 1 min slides the ticks toward the planet; screenshots ticks-*.png.
"""
import argparse,json,os,sys,tempfile,time,base64
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
from cdp import CDP
import rest_demo

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',default=str(Path(__file__).parent/'test-results/ticks'));args=p.parse_args()
    if os.environ.get('CDP_PORT','9333')=='9333':print('Refusing port 9333 (recording browser). Set CDP_PORT.');sys.exit(2)
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True);checks=[]
    def check(name,ok,detail=''):checks.append((name,bool(ok)));print(('PASS ' if ok else 'FAIL ')+name+(' — '+str(detail) if detail else ''),flush=True)
    with tempfile.TemporaryDirectory() as tmp:
        data=Path(tmp)/'fixture';rest_demo.prepare(data,'14:00')
        day=__import__('datetime').datetime.fromtimestamp(json.loads((data/'demo-fixture.json').read_text())['nowMillis']/1000).date()
        at=lambda hhmm:rest_demo.millis(day,hhmm)
        with rest_demo.services(data) as base:
            api=lambda path,body=None:rest_demo.request(base,path,body)
            api('/api/execution/demo/clock',{'setMillis':at('14:02')+30000})
            c=CDP();c.call('Page.enable');c.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':2,'mobile':True})
            c.js("localStorage.setItem('routine.language','en')");c.call('Page.navigate',{'url':base})
            def wait(expr,t=30):
                end=time.time()+t
                while time.time()<end:
                    if c.js('!!('+expr+')'):return True
                    time.sleep(.25)
                raise AssertionError('timeout: '+expr)
            def shot(name):(out/name).write_bytes(base64.b64decode(c.call('Page.captureScreenshot',{'format':'png'})['data']))
            ticks=lambda:c.js("JSON.stringify([...document.querySelectorAll('.orbit-scene .clock-tick')].map(e=>e.getAttribute('d')))")
            labels=lambda:c.js("[...document.querySelectorAll('.orbit-scene .clock-label')].map(e=>e.textContent).join(',')")
            wait("document.querySelector('.orbit-scene')")
            # routine level: the running routine's steps
            wait("document.querySelector('[data-show-parent]')")
            r=json.loads(ticks());check('routine level draws clock ticks (30 min window, 5 min)',5<=len(r)<=7,len(r))
            check('routine level labels sit on 10-minute marks',all(l.split(':')[1][1]=='0' for l in labels().split(',') if l),labels())
            shot('ticks-1-routine.png')
            # day level: My routine
            c.js("document.querySelector('[data-show-parent]').click()");wait("document.querySelector('.day-scene')");wait("!document.getAnimations().length")  # level-change camera: both orbits are on screen until it lands
            d=json.loads(ticks());check('My routine draws clock ticks (2 h window, 10 min; ~220° of the circle visible)',11<=len(d)<=16,len(d))
            check('My routine labels are whole hours',labels() and all(l.endswith(':00') for l in labels().split(',')),labels())
            shot('ticks-2-day.png')
            first=c.js("document.querySelector('.day-scene .clock-tick').getAttribute('d')")
            api('/api/execution/demo/clock',{'advanceMinutes':1})
            wait(f"document.querySelector('.day-scene .clock-tick')&&document.querySelector('.day-scene .clock-tick').getAttribute('d')!=={json.dumps(first)}",20)
            check('one minute later the ticks have slid (no reload)',True)
            api('/api/execution/demo/clock',{'advanceMinutes':9});time.sleep(6)
            shot('ticks-3-day-10min-later.png')
            check('labels still whole hours after 10 min',all(l.endswith(':00') for l in labels().split(',') if l),labels())
    fails=[n for n,ok in checks if not ok]
    print(('FAIL ' if fails else 'PASS ')+str(len(checks)-len(fails)));sys.exit(1 if fails else 0)

if __name__=='__main__':main()
