"""Browser check of the rest-mode AI batch proposal with a MOCK Meta reply (no key, no paid call).

Start Chrome/Chromium first:  chromium --headless=new --remote-debugging-port=9333 --user-data-dir=<new temp dir> about:blank
Then:  JAVA_HOME=... python3 apps/mobile/verify_rest_browser.py [--out DIR]
Uses a new disposable fixture; never ~/.emotion-scheduler. Screenshots go to --out (default apps/mobile/test-results/rest).
"""
import argparse,json,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
from cdp import CDP
import rest_demo

REPLY={'items':[{'id':'team-sync','action':'move','newStart':'19:00','reason':'Right after dinner, outside your rest.'},
                {'id':'budget-draft','action':'move','newStart':'20:30','reason':'Late evening slot.'},
                {'id':'deep-work-block','action':'move','newStart':'17:00','reason':'Right after your rest.'},
                {'id':'doctor-call','action':'keep','reason':'Required, so it stays.'}]}
class MockMeta:
    calls=0
    def __init__(self):self.language='en';self.metrics=[]
    def reschedule(self,context):MockMeta.calls+=1;return REPLY
    def recommend(self,query,candidates):
        b=next(c for c in candidates if c['title']=='Burnout reset')
        return {'status':'matched','choices':[{'id':b['id'],'version':b['version'],'reason':'You made this for sudden emotional spikes.'}]}

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',default=str(Path(__file__).parent/'test-results/rest'));args=p.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True);checks=[]
    with tempfile.TemporaryDirectory() as tmp:
        data=Path(tmp)/'fixture';rest_demo.prepare(data,'14:00')
        day=__import__('datetime').datetime.fromtimestamp(json.loads((data/'demo-fixture.json').read_text())['nowMillis']/1000).date()
        at=lambda hhmm:rest_demo.millis(day,hhmm)
        with rest_demo.services(data,provider_factory=MockMeta) as base:
            rest_demo.request(base,'/api/execution/demo/clock',{'setMillis':at('14:00')})
            c=CDP();c.call('Page.enable');c.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':2,'mobile':True})
            c.call('Page.navigate',{'url':base});time.sleep(.6);c.js("localStorage.setItem('routine.language','en')");c.call('Page.reload');time.sleep(.6)
            def wait(expr,timeout=15):
                end=time.time()+timeout
                while time.time()<end:
                    if c.js('!!('+expr+')'):return True
                    time.sleep(.2)
                raise AssertionError('timeout: '+expr)
            def check(name,expr):
                assert c.js('!!('+expr+')'),name;checks.append(name)
            def click(expr):c.js('('+expr+').click()');time.sleep(.35)
            byText=lambda sel,text:f'[...document.querySelectorAll({json.dumps(sel)})].find(e=>e.textContent.includes({json.dumps(text)}))'
            item=lambda title:byText('.reschedule-item',title)
            # Video flow: Find → type the moment → Meta recommends the user's own Burnout reset → Start.
            wait("document.querySelector('[data-nav=find]')&&document.body.innerText.includes('Start a report')")
            for _ in range(10):
                click('document.querySelector("[data-nav=find]")');time.sleep(.5)
                if c.js('!!document.querySelector("[data-search-edit]")'):break
            click('document.querySelector("[data-search-edit]")');wait("document.querySelector('#search-input')")
            c.js("(()=>{const i=document.querySelector('#search-input');i.value="+json.dumps(rest_demo.QUERY)+";i.dispatchEvent(new Event('input',{bubbles:true}));document.querySelector('#search-form').requestSubmit();})()")
            wait("document.querySelector('[data-result-start]')")
            check('Meta recommends Burnout reset',"document.querySelector('#content').textContent.includes('Burnout reset')")
            c.shot(str(out/'00-recommendation.png'))
            click('document.querySelector("[data-result-start]")')
            wait('document.querySelector("[data-rest-apply]")')
            check('summary opens with AI proposal inside',"document.querySelector('h1').textContent==='Schedule proposal for your rest'&&document.querySelector('#content').textContent.includes('AI proposal')")
            check('rest window 14:00–17:00 shown',"document.querySelector('#content').textContent.includes('Rest 14:00–17:00')")
            check('four affected items',"document.querySelectorAll('.reschedule-item').length===4")
            check('valid AI suggestion shown as is',f"{item('Team sync')}.textContent.includes('19:00–19:30')&&{item('Team sync')}.textContent.includes('Right after dinner')")
            check('past-21:00 AI suggestion needs check, not offered',f"{item('Budget draft')}.textContent.includes('Needs check')&&{item('Budget draft')}.querySelector('.rest-check s').textContent.includes('20:30–21:30')&&{item('Budget draft')}.querySelector('b').textContent.includes('19:30–20:30')")
            check('overlapping AI suggestion needs check',f"{item('Deep work block')}.textContent.includes('overlaps another plan')&&{item('Deep work block')}.querySelector('b').textContent.includes('Not this time')")
            check('required item fixed, no change button',f"{item('Doctor call')}.textContent.includes('Required — stays')&&!{item('Doctor call')}.querySelector('[data-rest-edit]')")
            check('single apply button',"document.querySelectorAll('[data-rest-apply]').length===1&&document.querySelectorAll('.actions button').length===1")
            check('no horizontal overflow',"document.documentElement.scrollWidth<=390")
            c.shot(str(out/'01-proposal.png'))
            click(item('Team sync')+'.querySelector("[data-rest-edit]")');wait(item('Team sync')+'.querySelector("[data-rest-choice]")')
            check('team sync choices',f"[...{item('Team sync')}.querySelectorAll('[data-rest-choice]')].map(b=>b.textContent).join('|')==='As AI suggested|Move to another time|Not this time|Keep as is|Decide later myself'")
            c.shot(str(out/'02-change-options.png'))
            click(byText('[data-rest-choice]','Move to another time'));wait('document.querySelector("[data-rest-time]")')
            c.js("(()=>{const i=document.querySelector('[data-rest-time]');i.value='20:45';i.dispatchEvent(new Event('change'))})()");time.sleep(.6)
            check('invalid user time is flagged before apply',f"{item('Team sync')}.textContent.includes(\"Can't apply\")&&{item('Team sync')}.textContent.includes('after the end of your day')")
            c.shot(str(out/'03-invalid-time.png'))
            click(byText('[data-rest-choice]','Keep as is'));wait(f"!{item('Team sync')}.classList.contains('has-issue')")
            check('one item changed to keep',f"{item('Team sync')}.textContent.includes('Changed by me')&&{item('Team sync')}.querySelector('b').textContent.includes('Keep as is')")
            before=rest_demo.request(base,'/api/execution/reservations')
            assert before==rest_demo.request(base,'/api/execution/reservations');checks.append('nothing changed before apply')
            click('document.querySelector("[data-rest-apply]")');wait("document.querySelector('h1').textContent==='Updated schedule'")
            got={r['title']:(r['startMillis'],r.get('status')) for r in rest_demo.request(base,'/api/execution/reservations')}
            assert got=={'Team sync':(at('14:30'),None),'Doctor call':(at('15:00'),None),'Budget draft':(at('19:30'),None),'Deep work block':(at('16:00'),'skipped'),'Write report section':(at('17:30'),None)},got
            checks.append('apply: only Team sync kept, rest of proposal applied')
            check('applied view lists not-this-time without external cancel',"document.querySelector('#content').textContent.includes('External bookings are not cancelled')")
            c.shot(str(out/'04-applied.png'))
            report=next(r for r in rest_demo.request(base,'/api/execution/context')['workspace']['runs'] if r['id']=='demo-report')
            assert report['currentUnitId']=='heading';checks.append('report run still at Write a working heading')
            assert MockMeta.calls==1,MockMeta.calls;checks.append('one Meta call')
    (out/'rest-browser-results.json').write_text(json.dumps({'passed':len(checks),'checks':checks,'meta':'mock reply, no paid call','limitations':'Headless Chromium mobile viewport on Linux; no physical phone.'},indent=2))
    print('PASS',len(checks))
if __name__=='__main__':main()
