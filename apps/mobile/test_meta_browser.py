"""Mobile viewport + real local KMP; provider fixture, no paid calls.
Requires an isolated Chrome debugging session on port 9333.
"""
import json,sys,time,threading,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
from cdp import CDP
from test_execution_integration import IntegrationFixture
from test_recommendation import Fake
from recommendation_service import RecommendationService
from store import DomainError
from meta_provider import MetaProvider
from test_meta_integration import Opener
from urllib.error import URLError

parser=argparse.ArgumentParser();parser.add_argument('--output',default='/tmp/meta-browser-results');parser.add_argument('--language',choices=['en','ko'],default='en');args=parser.parse_args()
output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
release=threading.Event()
class Fixture(Fake):
 mode='generate'
 def recommend(self,*args):
  if self.mode=='delay':release.wait(5)
  if self.mode=='error':return MetaProvider('synthetic-key',Opener(URLError(TimeoutError()))).recommend('synthetic',[])
  return {'status':'no_fit','choices':[]}
 def generate(self,query):
  return {'title':'외출 전 화분 확인하기','description':'먼저 상태를 확인해요.','steps':[{'id':'a','title':'흙 상태 확인하기'},{'id':'b','title':'마른 화분에 물 주기'}]}
fixture=Fixture();checks=[]
copy={'__DISCLOSURE__':'sent to Meta AI' if args.language=='en' else 'Meta AI로 보내','__PROPOSAL__':'New suggestion' if args.language=='en' else '새 제안','__NEXT__':'No upcoming tasks' if args.language=='en' else '다음 작업 없음','__TIMEOUT__':'taking too long' if args.language=='en' else '늦어지고'}
def localized(expr):
 for key,value in copy.items():expr=expr.replace(key,value)
 return expr
def wait(expr,seconds=8):
 expr=localized(expr)
 end=time.time()+seconds
 while time.time()<end:
  if c.js(expr):return
  time.sleep(.1)
 raise AssertionError(expr)
def check(name,expr):
 assert c.js(localized(expr)),name
 checks.append(name)
def click(selector):c.js('document.querySelector('+json.dumps(selector)+').click()')
def fill(value):c.js('(()=>{const e=document.querySelector("#search-input");e.value='+json.dumps(value)+';e.dispatchEvent(new Event("input",{bubbles:true}));})()')
IntegrationFixture.setUpClass()
try:
 IntegrationFixture.mobile.recommendations=RecommendationService(IntegrationFixture.mobile.store,lambda:fixture)
 c=CDP();c.call('Page.enable');c.call('Page.addScriptToEvaluateOnNewDocument',{'source':'localStorage.setItem("routine.language",'+json.dumps(args.language)+')'});c.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True});c.call('Page.navigate',{'url':IntegrationFixture.url})
 wait('!!document.querySelector("[data-new]")');click('[data-nav=find]');wait('!!document.querySelector("#search-input")')
 wait('!!document.querySelector("[data-open]")')
 check('disclosure before request','document.body.textContent.includes("__DISCLOSURE__")')
 fill('외출 전에 화분 확인');click('button[type=submit]')
 wait('document.body.textContent.includes("__PROPOSAL__")')
 check('preview is not library','document.querySelectorAll("[data-open]").length===1')
 assert IntegrationFixture.mobile.store.library()['items']==[];checks.append('preview does not save')
 c.shot(str(output/'meta-result.png'))
 click('[data-open]');wait('!!document.querySelector("[data-start]")')
 check('whole routine and attribution before start','document.querySelectorAll("li").length===2&&document.body.textContent.includes("Meta AI")')
 check('no horizontal overflow','document.documentElement.scrollWidth<=390')
 c.shot(str(output/'meta-detail.png'))
 click('[data-start]');wait('!!document.querySelector("[data-action=complete]")')
 check('first action visible','document.querySelector("h1").textContent==="흙 상태 확인하기"')
 assert len(IntegrationFixture.mobile.store.library()['items'])==1;checks.append('start accepts once')
 c.shot(str(output/'meta-current.png'))
 click('[data-action=complete]');wait('document.querySelector("h1").textContent==="마른 화분에 물 주기"')
 click('[data-action=complete]');wait('document.body.textContent.includes("__NEXT__")');checks.append('completion returns ordinary current screen')
 click('[data-nav=find]');wait('!!document.querySelector("#search-input")');fixture.mode='error';fill('오류 시험');click('button[type=submit]')
 wait('document.querySelector("#message").textContent.includes("__TIMEOUT__")')
 check('error preserves input without false result','document.querySelector("#search-input").value==="오류 시험"&&document.querySelectorAll("[data-open]").length===0')
 fixture.mode='delay';fill('취소 시험');click('button[type=submit]');wait('!!document.querySelector("[data-cancel-search]")');click('[data-cancel-search]');release.set();time.sleep(.5)
 check('cancel suppresses late result','document.querySelectorAll("[data-open]").length===0&&document.querySelector("#search-input").value==="취소 시험"')
 fixture.mode='delay';release.clear();fill('이동 시험');click('button[type=submit]');wait('!!document.querySelector("[data-cancel-search]")');click('[data-nav=library]');wait('!!document.querySelector("[data-new]")');release.set();time.sleep(.5)
 check('navigation survives late response','!!document.querySelector("[data-new]")&&!document.querySelector("#search-input")')
 output.joinpath('browser-results.json').write_text(json.dumps({'passed':len(checks),'language':args.language,'checks':checks,'limitations':'Synthetic provider; real local KMP; desktop Chrome 390x844, not physical phone or watch.'},ensure_ascii=False,indent=2))
 print('PASS',len(checks))
finally:
 release.set();IntegrationFixture.tearDownClass()
