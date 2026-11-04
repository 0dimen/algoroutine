"""Browser check of + Add → Google Calendar (secret iCal address, read-only). Local fixture calendar, no Google, no Meta.

Start a SEPARATE headless Chrome first (never the recording one):
  "Google Chrome" --headless=new --remote-debugging-port=9336 --user-data-dir=<new temp dir> about:blank
Then:  CDP_PORT=9336 python3 apps/mobile/verify_google_browser.py [--out DIR]
Uses a new disposable rest_demo fixture (demo clock 14:00) on temporary ports and serves rest_demo.google_ics at /demo/google.ics.

Selectors for recording scripts: [data-day-add] → [data-add-kind=google] → #google-url → [data-google-import].
Inline error: #google-error. Imported items carry .tag-google ("Google").
"""
import argparse,json,os,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
from cdp import CDP
import rest_demo

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',default=str(Path(__file__).parent/'test-results/google'));args=p.parse_args()
    if os.environ.get('CDP_PORT','9333')=='9333':print('Refusing port 9333 (recording browser). Set CDP_PORT.');sys.exit(2)
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True);checks=[]
    with tempfile.TemporaryDirectory() as tmp:
        data=Path(tmp)/'fixture';rest_demo.prepare(data,'14:00');day=rest_demo.fixture_day(data);at=lambda hhmm:rest_demo.millis(day,hhmm)
        ics=Path(tmp)/'demo-google.ics';ics.write_text(rest_demo.google_ics(day))
        with rest_demo.services(data,demo_ics=str(ics)) as base:
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
            def shot(name):c.shot(str(out/('google-'+name+'.png')))
            h1="document.querySelector('#content h1')?.textContent"
            def to_day_level():
                if not c.js("!!document.querySelector('.day-scene')"):click('.orbit-parent');wait("document.querySelector('.day-scene')")
            wait("document.querySelector('.orbit-parent')");to_day_level()
            click('[data-day-add]');wait("document.querySelector('[data-add-kind=google]')")
            check('third choice: Google Calendar',"document.querySelector('[data-add-kind=google]').textContent.includes('Google Calendar')")
            shot('1-choice')
            click('[data-add-kind=google]');wait("document.querySelector('#google-url')")
            check('address field and hint',"document.querySelector('label[for=google-url]').textContent==='Secret address in iCal format'&&document.body.textContent.includes('Google Calendar → Settings → your calendar → Secret address in iCal format')")
            check('no horizontal overflow',"document.documentElement.scrollWidth<=390")
            shot('2-form')
            before=api('/api/execution/reservations')
            click('[data-google-import]');time.sleep(.3)
            check('empty address: inline message',"!document.querySelector('#google-error').hidden&&document.querySelector('#google-error').textContent==='Check the iCal address.'")
            setv('#google-url','http://example.com/basic.ics');click('[data-google-import]');time.sleep(.5)
            check('non-https address refused inline',"!document.querySelector('#google-error').hidden&&document.querySelector('#google-url')")
            assert api('/api/execution/reservations')==before;checks.append('nothing saved on errors')
            setv('#google-url',base+'/demo/google.ics');click('[data-google-import]');wait("document.querySelector('.day-scene')")
            check('toast: 2 plans added',"document.querySelector('.completion-toast')?.textContent==='2 plans added from Google Calendar'")
            check('first imported plan shown with Google tag',h1+"==='Dinner with Mina'&&document.querySelector('.focus-meta .tag-google')?.textContent==='Google'&&document.querySelector('.focus-meta').textContent.includes('21:00–22:00')")
            shot('3-day-after-import')
            got=[r for r in api('/api/execution/reservations') if r['id'].startswith('gcal-')]
            assert sorted((r['title'],r['startMillis'],r['endMillis'],r['required'],r['movable'],r['kind']) for r in got)==sorted([('Dinner with Mina',at('21:00'),at('22:00'),True,False,'schedule'),('Call with Dad',at('22:30'),at('23:00'),True,False,'schedule')]),got
            checks.append('saved as Required plain schedules (time cannot change)')
            click('[data-day-open]');wait("document.querySelector('[data-reservation]')")
            check('detail shows Google tag',"document.querySelector('#content .tag-google')?.textContent==='Google'")
            shot('4-detail')
            click('[data-day-back]');time.sleep(.4)
            # Re-import: saved address (left empty) → nothing duplicated.
            to_day_level();click('[data-day-add]');wait("document.querySelector('[data-add-kind=google]')");click('[data-add-kind=google]');wait("document.querySelector('#google-url')")
            check('saved address note',"document.body.textContent.includes('An address is saved')")
            click('[data-google-import]');wait("document.querySelector('.day-scene')")
            check('re-import: nothing duplicated',"document.querySelector('.completion-toast')?.textContent==='2 already in My routine'")
            assert len([r for r in api('/api/execution/reservations') if r['id'].startswith('gcal-')])==2;checks.append('still 2 imported plans')
            saved=(data/'google-calendar.json').read_text();assert '/demo/google.ics' in saved and 'url' not in api('/api/calendar/google');checks.append('address kept only in the local data dir')
            c.js("localStorage.setItem('routine.language','ko')");c.call('Page.reload');time.sleep(1);to_day_level()
            click('[data-day-add]');wait("document.querySelector('[data-add-kind=google]')")
            check('ko: 구글 캘린더 choice',"document.querySelector('[data-add-kind=google]').textContent.includes('구글 캘린더')")
            shot('5-ko-choice')
    (out/'google-browser-results.json').write_text(json.dumps({'passed':len(checks),'checks':checks,'meta':'off (no paid call)','google':'local fixture only'},indent=2))
    print('PASS',len(checks))
if __name__=='__main__':main()
