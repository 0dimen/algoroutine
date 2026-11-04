"""Browser check of "+ Add" at the day level (plain schedule / routine, always start–end). No Meta, no paid call.

Start a SEPARATE headless Chrome first (never the recording one):
  "Google Chrome" --headless=new --remote-debugging-port=9334 --user-data-dir=<new temp dir> about:blank
Then:  CDP_PORT=9334 JAVA_HOME=... python3 apps/mobile/verify_add_browser.py [--out DIR]
Uses a new disposable rest_demo fixture (demo clock 14:00) on temporary ports; never ~/.emotion-scheduler.

Selectors for recording scripts: [data-day-add] → [data-add-kind=schedule|routine] → (routine: [data-add-routine=<id>])
→ #schedule-title (schedule only), #schedule-start, #schedule-end (type=time, today), #schedule-required, #schedule-movable,
#schedule-deadline → [data-schedule-save]. Inline error: #schedule-error. Back: [data-add-back].
"""
import argparse,json,os,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
from cdp import CDP
import rest_demo

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',default=str(Path(__file__).parent/'test-results/add'));p.add_argument('--prefix',default='add-');args=p.parse_args()
    if os.environ.get('CDP_PORT','9333')=='9333':print('Refusing port 9333 (recording browser). Set CDP_PORT.');sys.exit(2)
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True);checks=[]
    with tempfile.TemporaryDirectory() as tmp:
        data=Path(tmp)/'fixture';fixture=rest_demo.prepare(data,'14:00')
        day=__import__('datetime').datetime.fromtimestamp(json.loads((data/'demo-fixture.json').read_text())['nowMillis']/1000).date()
        at=lambda hhmm:rest_demo.millis(day,hhmm)
        with rest_demo.services(data) as base:
            api=lambda path,body=None:rest_demo.request(base,path,body)
            api('/api/execution/demo/clock',{'setMillis':at('14:00')})
            c=CDP();c.call('Page.enable');c.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':2,'mobile':True})
            c.call('Page.navigate',{'url':base});time.sleep(.6);c.js("localStorage.setItem('routine.language','en')");c.call('Page.reload');time.sleep(.8)
            def wait(expr,timeout=15):
                end=time.time()+timeout
                while time.time()<end:
                    if c.js('!!('+expr+')'):return True
                    time.sleep(.2)
                raise AssertionError('timeout: '+expr)
            def check(name,expr):
                assert c.js('!!('+expr+')'),name;checks.append(name)
            def click(sel):c.js(f'document.querySelector({json.dumps(sel)}).click()');time.sleep(.4)
            def setv(sel,value):c.js(f"(()=>{{const i=document.querySelector({json.dumps(sel)});i.value={json.dumps(value)};i.dispatchEvent(new Event('input',{{bubbles:true}}));}})()")
            def shot(name):c.shot(str(out/(args.prefix+name+'.png')))
            h1="document.querySelector('#content h1')?.textContent"
            def to_day_level():
                if not c.js("!!document.querySelector('.day-scene')"):click('.orbit-parent');wait("document.querySelector('.day-scene')")
            wait("document.querySelector('.orbit-parent')")
            to_day_level()
            check('day level shows + Add',"document.querySelector('[data-day-add]')?.textContent.includes('Add')")
            click('[data-day-add]');wait("document.querySelector('[data-add-kind=schedule]')")
            check('choice: Schedule and Routine',"document.querySelector('[data-add-kind=schedule]').textContent.includes('Schedule')&&document.querySelector('[data-add-kind=routine]').textContent.includes('Routine')")
            shot('1-choice')
            click('[data-add-kind=schedule]');wait("document.querySelector('#schedule-title')")
            check('prefill: next half hour, 30 min',"document.querySelector('#schedule-start').value==='14:30'&&document.querySelector('#schedule-end').value==='15:00'")
            check('defaults: not required, time can change',"!document.querySelector('#schedule-required').checked&&document.querySelector('#schedule-movable').checked&&document.querySelector('#schedule-deadline').value===''")
            before=api('/api/execution/reservations')
            setv('#schedule-title','Team sync');setv('#schedule-start','17:00');setv('#schedule-end','16:30')
            click('[data-schedule-save]');time.sleep(.3)
            check('end before start: inline message',"!document.querySelector('#schedule-error').hidden&&document.querySelector('#schedule-error').textContent==='End time must be after the start time.'&&document.querySelector('#schedule-title')")
            setv('#schedule-end','17:00');click('[data-schedule-save]');time.sleep(.3)
            check('end equal to start: inline message',"!document.querySelector('#schedule-error').hidden")
            assert api('/api/execution/reservations')==before;checks.append('invalid times not saved')
            shot('2c-invalid')
            setv('#schedule-end','17:30');time.sleep(.2)
            check('message hides while editing',"document.querySelector('#schedule-error').hidden")
            check('no horizontal overflow (form)',"document.documentElement.scrollWidth<=390")
            shot('2-schedule-form')
            click('[data-schedule-save]');wait("document.querySelector('.day-scene')")
            check('back at day level with message',"document.querySelector('.completion-toast')?.textContent==='Added to My routine'")
            check('new item shown',h1+"==='Team sync'&&document.querySelector('.focus-meta').textContent.includes('17:00–17:30')")
            shot('4-day-after-schedule')
            saved=[r for r in api('/api/execution/reservations') if r.get('kind')=='schedule']
            assert len(saved)==1 and (saved[0]['title'],saved[0]['startMillis'],saved[0]['endMillis'])==('Team sync',at('17:00'),at('17:30')),saved
            checks.append('saved as plain schedule 17:00–17:30')
            ids=[x['id'] for x in api('/api/execution/context')['day']]
            assert ids.index('deep-work-block')<ids.index(saved[0]['id'])<ids.index('write-report-section'),ids;checks.append('day list in time order')
            c.call('Page.reload');time.sleep(1);wait("document.querySelector('.orbit-parent')")
            assert saved[0]['id'] in [x['id'] for x in api('/api/execution/context')['day']];checks.append('kept after reload')
            # Routine: pick Burnout reset, 20:00–21:00.
            to_day_level();click('[data-day-add]');wait("document.querySelector('[data-add-kind=routine]')")
            click('[data-add-kind=routine]');wait("document.querySelector('[data-add-routine]')")
            check('routine list has Burnout reset',f"document.querySelector('[data-add-routine=\"{fixture['burnout']['id']}\"]')?.textContent.includes('Burnout reset')")
            shot('3-routine-pick')
            click(f"[data-add-routine=\"{fixture['burnout']['id']}\"]");wait("document.querySelector('#schedule-start')")
            check('routine form has no title field',"!document.querySelector('#schedule-title')&&"+h1+"==='Burnout reset'")
            setv('#schedule-start','20:00');setv('#schedule-end','21:00');shot('3b-routine-form')
            click('[data-schedule-save]');wait("document.querySelector('.day-scene')")
            check('routine added message',"document.querySelector('.completion-toast')?.textContent==='Added to My routine'")
            shot('4b-day-after-routine')
            burn=next(r for r in api('/api/execution/reservations') if r['definitionId']==fixture['burnout']['id'])
            assert (burn['kind'],burn['title'],burn['startMillis'],burn['endMillis'])==('routine','Burnout reset',at('20:00'),at('21:00')),burn;checks.append('saved as routine reservation')
            # Plain schedule at 17:00: never starts by itself; Start → current with Done; Done → completed.
            api('/api/execution/demo/clock',{'setMillis':at('17:02')});c.call('Page.reload');time.sleep(1);wait("document.querySelector('.orbit-parent')")
            occ='reserved-'+saved[0]['id']
            assert occ not in [r['id'] for r in api('/api/execution/context')['workspace']['runs']];checks.append('plain schedule does not start by itself')
            to_day_level()
            for _ in range(10):
                if c.js(h1+"==='Team sync'&&document.querySelector('.focus-meta').textContent.includes('17:00–17:30')"):break
                c.js("document.querySelector('.orbit-position-2')?.click()");time.sleep(.35)
            check('browse to Team sync 17:00 on the day orbit',h1+"==='Team sync'&&document.querySelector('.focus-meta').textContent.includes('17:00–17:30')")
            shot('4c-day-plain-ready')
            click('[data-day-open]');wait("document.querySelector('[data-reservation]:not([disabled])')")
            check('detail shows Schedule pill',"document.querySelector('.pill').textContent.startsWith('Schedule')")
            click('[data-reservation]');wait("document.querySelector('[data-action=completeParent]')")
            check('running plain schedule shows Done at the day level',h1+"==='Team sync'&&document.querySelector('.day-scene')&&document.querySelector('.focus-meta').textContent.includes('In progress')")
            shot('5-plain-running')
            click('[data-action=completeParent]');time.sleep(.6)
            run=next(r for r in api('/api/execution/context')['workspace']['runs'] if r['id']==occ)
            assert run['status']=='completed',run;checks.append('Done completes the plain schedule')
            # Routine at 20:00 starts its steps.
            api('/api/execution/demo/clock',{'setMillis':at('20:00')})
            w=api('/api/execution/context')['workspace']
            outp=api('/api/execution/command',{'id':'start-burn','kind':'start','occurrenceId':burn['occurrenceId'],'expectedRevision':w['revision'],'definition':{'id':burn['definitionId'],'version':burn['definitionVersion'],'title':'','author':'','steps':[]}})
            r=next(x for x in outp['context']['workspace']['runs'] if x['id']==burn['occurrenceId'])
            assert r['currentUnitId']=='phone' and len(r['steps'])==3;checks.append('routine reservation starts its steps at 20:00')
            # Korean message.
            c.js("localStorage.setItem('routine.language','ko')");c.call('Page.reload');time.sleep(1)
            check('ko + Add label',"document.querySelector('[data-day-add]')?.textContent.includes('추가')||!document.querySelector('.day-scene')")
    (out/'add-browser-results.json').write_text(json.dumps({'passed':len(checks),'checks':checks,'meta':'off (no paid call)','limitations':'Headless Chrome mobile viewport on macOS; no physical phone.'},indent=2))
    print('PASS',len(checks))
if __name__=='__main__':main()
