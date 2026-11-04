"""Real browser audio pipeline; --live-voice explicitly spends on synthetic ASR.
Chrome must run with fake microphone WAV and CDP 9333. Recommendation is a fixture.
"""
import argparse,json,sys,time,queue,base64,array,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
from cdp import CDP
from test_execution_integration import IntegrationFixture
from recommendation_service import RecommendationService
from voice import VoiceManager,VoiceSession,meta_voice_session

parser=argparse.ArgumentParser();parser.add_argument('--live-voice',action='store_true');parser.add_argument('--output',default='/tmp/voice-browser');args=parser.parse_args()
output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
requests=[]
class Rank:
 def recommend(self,query,candidates):requests.append(query);return {'status':'matched','choices':[{'id':'report-start','version':1,'reason':'문서 시작에 맞는 순서입니다.'}]}
 def generate(self,query):raise AssertionError('unexpected generation')
class Socket:
 def __init__(self):self.q=queue.Queue();self.n=0
 def recv(self):return self.q.get(timeout=5)
 def send_binary(self,raw):
  self.n+=1
  self.q.put(json.dumps({'type':'transcript','transcript':'보고서' if self.n<3 else '보고서 작성을 시작하고 싶어요.','final':False}))
 def send(self,raw):self.q.put(json.dumps({'type':'transcript','transcript':'보고서 작성을 시작하고 싶어요.','final':True}))
 def close(self,timeout=0):self.q.put('')
checks=[]
def wait(expr,seconds=10):
 end=time.time()+seconds
 while time.time()<end:
  if c.js(expr):return
  time.sleep(.1)
 raise AssertionError(expr+' | '+str(c.js('document.querySelector(".voice-note")?.textContent')))
def check(name,expr):assert c.js(expr),name;checks.append(name)
def click(selector):c.js('document.querySelector('+json.dumps(selector)+').click()')
def fill(text):c.js('(()=>{const e=document.querySelector("#search-input");e.value='+json.dumps(text)+';e.dispatchEvent(new Event("input",{bubbles:true}));})()')
IntegrationFixture.setUpClass()
try:
 server=IntegrationFixture.mobile;server.recommendations=RecommendationService(server.store,Rank)
 server.voice=VoiceManager(meta_voice_session if args.live_voice else lambda:VoiceSession(Socket()))
 levels=[]
 original_action=server.voice.action
 def traced(action,body):
  if action=='chunk':
   samples=array.array('h',base64.b64decode(body['audio']));levels.append(max(abs(x) for x in samples))
  try:return original_action(action,body)
  except Exception:
   print('VOICE_FAILURE',action,body.get('seq'),server.voice.current.seq if server.voice.current else None,flush=True);raise
 server.voice.action=traced
 c=CDP();c.call('Page.enable');c.call('Page.addScriptToEvaluateOnNewDocument',{'source':"localStorage.setItem('routine.language','ko')"});c.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
 c.call('Browser.grantPermissions',{'origin':IntegrationFixture.url,'permissions':['audioCapture']})
 c.call('Page.navigate',{'url':IntegrationFixture.url});wait('!!document.querySelector("[data-new]")');click('[data-nav=find]');wait('!!document.querySelector("[data-voice-main]")')
 click('[data-voice-main]');wait('document.querySelector("[data-voice-main]").getAttribute("aria-label")==="말하기 종료"')
 wait('document.querySelector(".voice-live").textContent.includes("보고서")',12)
 check('partial appears during recording','document.querySelector("#search-input").disabled')
 c.shot(str(output/'voice-listening.png'))
 if args.live_voice:time.sleep(3)
 click('[data-voice-main]');wait('!document.querySelector("#search-input").disabled',16)
 check('review not automatic recommendation','document.querySelector("#search-input").value.includes("보고서")&&document.querySelectorAll("[data-open]").length<=1')
 assert requests==[];checks.append('no recommendation before explicit submit')
 c.shot(str(output/'voice-review.png'))
 fill('내가 수정한 문서 시작 요청');click('button[type=submit]');wait('!!document.querySelector("[data-open]")')
 assert requests==['내가 수정한 문서 시작 요청'];checks.append('edited text is exact recommendation input')
 click('[data-open]');wait('!!document.querySelector("[data-start]")');click('[data-start]');wait('!!document.querySelector("[data-action=complete]")')
 check('voice recommendation starts real KMP','document.querySelector("h1").textContent==="새 문서 열기"')
 c.shot(str(output/'voice-current.png'))
 click('[data-action=complete]');wait('document.querySelector("h1").textContent==="소제목 세 개 적기"');checks.append('completion advances')
 click('[data-nav=find]');wait('!!document.querySelector("[data-voice-main]")')
 # Remaining UI edge cases use a deterministic provider, not additional paid audio.
 server.voice.close();server.voice=VoiceManager(lambda:VoiceSession(Socket()))
 fill('기존 입력 유지');click('[data-voice-main]');wait('!!document.querySelector("[data-voice-cancel]")');click('[data-voice-cancel]');time.sleep(.3)
 check('cancel retains original text','document.querySelector("#search-input").value==="기존 입력 유지"&&!document.querySelector("#search-input").disabled')
 c.call('Browser.setPermission',{'origin':IntegrationFixture.url,'permission':{'name':'microphone'},'setting':'denied'})
 click('[data-voice-main]');wait('document.querySelector(".voice-note").textContent.includes("권한")')
 check('denial retains editable text','!document.querySelector("#search-input").disabled&&document.querySelector("#search-input").value==="기존 입력 유지"')
 c.call('Browser.setPermission',{'origin':IntegrationFixture.url,'permission':{'name':'microphone'},'setting':'granted'})
 class SilentSocket(Socket):
  def send_binary(self,raw):pass
  def send(self,raw):self.q.put(json.dumps({'type':'transcript','transcript':'','final':True}))
 server.voice.close();server.voice=VoiceManager(lambda:VoiceSession(SilentSocket()))
 click('[data-voice-main]');wait('document.querySelector("[data-voice-main]").getAttribute("aria-label")==="말하기 종료"');time.sleep(.3);click('[data-voice-main]')
 wait('document.querySelector(".voice-note").textContent.includes("말소리")')
 check('silence preserves editable input','document.querySelector("#search-input").value==="기존 입력 유지"&&!document.querySelector("#search-input").disabled')
 # Finishing must survive the old 8-second listening inactivity deadline.
 class LateSocket(Socket):
  def send(self,raw):threading.Timer(9.2,lambda:self.q.put(json.dumps({'type':'transcript','transcript':'늦게 도착한 최종 문장','final':True}))).start()
  def recv(self):return self.q.get(timeout=15)
 server.voice.close();server.voice=VoiceManager(lambda:VoiceSession(LateSocket()))
 fill('');click('[data-voice-main]');wait('document.querySelector(".voice-live").textContent.includes("보고서")')
 click('[data-voice-main]');wait('document.querySelector("#search-input").value==="늦게 도착한 최종 문장"',16)
 check('final after nine seconds stays editable','!document.querySelector("#search-input").disabled')
 class DisconnectSocket(Socket):
  def send(self,raw):
   self.q.put(json.dumps({'type':'transcript','transcript':'단절 직전 마지막 문장','final':False}));self.q.put('')
 server.voice.close();server.voice=VoiceManager(lambda:VoiceSession(DisconnectSocket()))
 fill('앞 문장');click('[data-voice-main]');wait('document.querySelector(".voice-live").textContent.includes("보고서")')
 click('[data-voice-main]');wait('document.querySelector(".voice-note").textContent.includes("끊겼")')
 check('disconnect preserves latest partial in browser','document.querySelector("#search-input").value==="앞 문장 단절 직전 마지막 문장"&&!document.querySelector("#search-input").disabled')
 server.voice.close();server.voice=VoiceManager(lambda:VoiceSession(Socket()))
 click('[data-voice-main]');wait('document.querySelector("[data-voice-main]").getAttribute("aria-label")==="말하기 종료"');click('[data-nav=library]');wait('!!document.querySelector("[data-new]")');time.sleep(.5)
 check('navigation remains after late voice result','!document.querySelector("#search-input")')
 assert server.voice.current.snapshot()['state']=='cancelled';checks.append('navigation closes voice session')
 output.joinpath('results.json').write_text(json.dumps({'passed':len(checks),'checks':checks,'liveASR':args.live_voice,'recommendation':'fixture','execution':'real local KMP','device':'headless Chrome mobile viewport, synthetic microphone'},ensure_ascii=False,indent=2));print('PASS',len(checks))
finally:
 print('AUDIO_PEAK',max(levels or [0]),'CHUNKS',len(levels),flush=True)
 if IntegrationFixture.mobile.voice:IntegrationFixture.mobile.voice.close()
 IntegrationFixture.tearDownClass()
