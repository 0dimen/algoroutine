"""English default / Korean switch / content preservation / reconnect regression.
Uses isolated real KMP + fake recommendation. No paid calls or user data.
"""
import json,sys,time,argparse
from pathlib import Path
from urllib.request import Request,urlopen
ROOT=Path(__file__).resolve().parents[2]
from cdp import CDP
from test_execution_integration import IntegrationFixture
p=argparse.ArgumentParser();p.add_argument('--output',default='/tmp/language-browser');a=p.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
checks=[]
def wait(expr,seconds=12):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  if c.js(expr):return
  time.sleep(.1)
 raise AssertionError(expr)
def check(name,expr):assert c.js(expr),name;checks.append(name)
def click(s):c.js('document.querySelector('+json.dumps(s)+').click()')
def language(code):c.js('(()=>{const e=document.querySelector("#app-language");e.value='+json.dumps(code)+';e.dispatchEvent(new Event("change",{bubbles:true}));})()')
IntegrationFixture.setUpClass()
try:
 c=CDP();c.call('Page.enable');c.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
 c.call('Page.navigate',{'url':IntegrationFixture.url});wait('!!document.querySelector("[data-new]")')
 check('new install defaults to English','document.documentElement.lang==="en"&&document.querySelector("h1").textContent==="Routine library"')
 click('[data-new]');wait('!!document.querySelector("#title")')
 c.js('(()=>{document.querySelector("#title").value="현재 — my original title";document.querySelector("#description").value="Original 설명";document.querySelector("[data-step]").value="사용자 행동 unchanged";document.querySelector("#editor").dispatchEvent(new Event("input",{bubbles:true}));})()')
 language('ko');check('switch preserves unsaved input','document.querySelector("#title").value==="현재 — my original title"&&document.querySelector("h1").textContent==="루틴 만들기"')
 language('en');check('switch back preserves original step','document.querySelector("[data-step]").value==="사용자 행동 unchanged"&&document.querySelector("h1").textContent==="Create routine"')
 c.js('document.querySelector("#editor").requestSubmit()');wait('!!document.querySelector("[data-save]")');click('[data-save]');wait('!!document.querySelector("[data-start]")');click('[data-start]');wait('!!document.querySelector("[data-action=complete]")')
 check('English action with original Korean content','document.querySelector("h1").textContent==="사용자 행동 unchanged"&&document.querySelector("[data-action=complete]").textContent.includes("Done")')
 c.shot(str(out/'mobile-english.png'))
 language('ko');check('Korean action without mutating routine','document.querySelector("h1").textContent==="사용자 행동 unchanged"&&document.querySelector("[data-action=complete]").textContent.includes("완료")')
 c.call('Page.reload');wait('!!document.querySelector("[data-new]")');check('selection survives reload','document.documentElement.lang==="ko"')
 language('en');click('[data-nav=current]');wait('!!document.querySelector("[data-action=complete]")')
 original=IntegrationFixture.mobile.execution_url;IntegrationFixture.mobile.execution_url='http://127.0.0.1:1'
 wait('document.querySelector("#message").dataset.kind==="execution-connection"',12)
 check('connection error is English','document.querySelector("#message").textContent.includes("Connection lost")')
 IntegrationFixture.mobile.execution_url=original;click('[data-execution-refresh]');wait('document.querySelector("#message").textContent===""')
 checks.append('successful refresh clears only connection warning')
 c.shot(str(out/'mobile-recovered.png'))
 # HTTP validation error follows the selected language, not the routine language.
 for lang,fragment in [('en','Enter'),('ko','입력')]:
  req=Request(IntegrationFixture.url+'/api/search',data=json.dumps({'query':'x'*501}).encode(),headers={'Content-Type':'application/json','X-Routine-App':'local','X-Routine-Language':lang})
  try:urlopen(req)
  except Exception as e:
   body=json.load(e);assert not any(k in body for k in ['routine','workspace']);assert ('characters' in body['error']['message']) if lang=='en' else ('입력' in body['error']['message'])
  else:raise AssertionError('invalid request accepted')
 checks.append('server validation errors follow language')
 out.joinpath('results.json').write_text(json.dumps({'passed':len(checks),'checks':checks,'model':'fixture/no calls','engine':'real KMP'},ensure_ascii=False,indent=2));print('PASS',len(checks))
finally:IntegrationFixture.tearDownClass()
