import sys,time,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
from cdp import CDP
import tempfile,threading
from server import make_server
temporary=tempfile.TemporaryDirectory();server=make_server(Path(temporary.name)/'browser.sqlite3',0);threading.Thread(target=server.serve_forever,daemon=True).start()
base='http://127.0.0.1:'+str(server.server_port)
evidence=Path(__file__).parent/'test-results';evidence.mkdir(exist_ok=True)
c=CDP();c.call('Page.enable');c.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True});c.call('Page.navigate',{'url':base});time.sleep(.4)
checks=[]
def check(name,expr):
 assert c.js(expr),name
 checks.append(name)
def click(selector):c.js('document.querySelector('+json.dumps(selector)+').click()');time.sleep(.25)
def fill(selector,value):c.js('(()=>{let e=document.querySelector('+json.dumps(selector)+');e.value='+json.dumps(value)+';e.dispatchEvent(new Event("input",{bubbles:true}));})()')
click('[data-new]');fill('#title','내가 만든 열 글자 넘는 루틴');fill('#description','긴 설명을 그대로 저장합니다.');fill('[data-step]','문서 열기');click('[data-add]');fill('.step:last-child input','한 줄 적기');click('[data-draft]');check('draft saved','document.querySelector("#message").textContent.includes("초안을 저장")')
c.call('Page.reload');time.sleep(.3);click('[data-new]');check('draft restored after reload','document.querySelector("#title").value==="내가 만든 열 글자 넘는 루틴"&&document.querySelectorAll("[data-step]").length===2')
click('button[type=submit]');check('preview all steps','document.querySelectorAll("li").length===2');click('[data-save]');check('real save acknowledged','document.querySelector("#message").textContent.includes("보관함에 저장했습니다")')
c.call('Page.reload');time.sleep(.3);check('saved routine restored after reload','document.querySelector("#content").textContent.includes("내가 만든 열 글자 넘는 루틴")');click('[data-open]');click('[data-edit]');fill('#title','수정한 내 루틴');click('button[type=submit]');click('[data-save]');check('edit saved as latest','document.querySelector("h1").textContent==="수정한 내 루틴"')
click('[data-nav=catalog]');click('[data-open]');check('catalog shows whole routine','document.querySelectorAll("li").length===3');click('[data-collect]');check('copied author preserved','document.querySelector("#content").textContent.includes("루틴 스튜디오")');click('[data-nav=library]');check('own and collected both visible','document.querySelectorAll("[data-open]").length===2');click('[data-filter=collected]');check('filter collected','document.querySelectorAll("[data-open]").length===1');check('no horizontal overflow','document.documentElement.scrollWidth<=390');c.shot(str(evidence/'mobile-library.png'))
# A failed/conflicting write must not pretend that a save succeeded.
click('[data-filter=mine]');click('[data-open]');click('[data-edit]');fill('#title','내 초안은 남아 있어야 함');click('button[type=submit]')
c.js("fetch('/api/library').then(r=>r.json()).then(d=>{let r=d.items.find(x=>x.source==='mine');return fetch('/api/commands',{method:'POST',headers:{'Content-Type':'application/json','X-Routine-App':'local'},body:JSON.stringify({commandId:crypto.randomUUID(),kind:'saveDefinition',definitionId:r.id,expectedVersion:r.version,content:{...r,title:'다른 창의 변경'}})})})")
time.sleep(.3);click('[data-save]');check('conflict explicit with draft preserved','document.querySelector("#message").textContent.includes("다른 창")&&document.querySelector("h1").textContent==="내 초안은 남아 있어야 함"')
(evidence/'browser-results.json').write_text(json.dumps({'passed':len(checks),'checks':checks,'limitations':'Desktop Chrome mobile viewport; no physical phone or watch input.'},ensure_ascii=False,indent=2));print('PASS',len(checks))

server.shutdown();server.server_close();temporary.cleanup()
