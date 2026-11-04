import {t, locale, setLocale, stepCount, languages} from '/i18n.js';
import {VoiceCapture} from '/voice.js';
const $=s=>document.querySelector(s), escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let optionLayer=null,optionOrigin=null,holdTimer=null,holdPoint=null,suppressUntil=0;
const state={view:'current',findMode:'home',resultIndex:0,resultFilter:'all',showParent:false,items:[],catalog:[],selected:null,filter:'all',draft:null,draftKey:null,draftRevision:0,pending:null,busy:false,execution:null,executionPending:null,searchDraft:'',searchQuery:'',searchItems:null,searchCount:3,searchLoading:false,detailReturn:null};
const voice=new VoiceCapture({onState:s=>{state.voice=s;if(state.view==='find'){const mode=['permission','listening','finishing'].includes(s.state)?'listening':['review','error'].includes(s.state)||s.state==='idle'&&state.findMode==='listening'?'review':state.findMode;if(mode!==state.findMode){state.findMode=mode;render();}else paintVoice();}},onDraft:text=>{state.searchDraft=text;const field=$('#search-input');if(field)field.value=text;}});
function voiceBusy(){return ['permission','listening','finishing'].includes(voice.state);}
function paintVoice(){
 const panel=$('#voice-panel');if(!panel)return;
 const busy=voiceBusy(),listening=voice.state==='listening';
 $('#content').querySelectorAll('.quick-routines,.recommendation-stack,h2,[data-search-more]').forEach(el=>el.hidden=busy);
 panel.innerHTML=`<div class="voice-controls"><button type="button" class="voice-mic" data-voice-main aria-label="${listening?(t("말하기 종료")):(t("말하기"))}" ${busy&&!listening?'disabled':''}>${listening?'■':'<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3M8 22h8"/></svg>'}</button>${busy?("<button type=\"button\" data-voice-cancel>"+t("취소")+"</button>"):''}</div><p class="voice-live" role="status" aria-live="polite"></p><small class="voice-note"></small>`;
 panel.querySelector('.voice-live').innerHTML=busy?voice.text.split(/(\s+)/).map(w=>`<span>${escape(w)}</span>`).join(''):'';
 panel.querySelector('.voice-note').textContent=state.voice?.note||(t("말하는 동안 음성을 Meta로 전송합니다. 이 앱에는 녹음을 저장하지 않습니다."));
 const field=$('#search-input');if(field)field.disabled=busy;
 const submit=$('#search-form button[type=submit]');if(submit)submit.disabled=busy||state.searchLoading;
 panel.querySelector('[data-voice-main]').onclick=()=>{if(state.searchLoading)return;if(listening)voice.stop();else voice.start(state.searchDraft);};
 panel.querySelector('[data-voice-cancel]')?.addEventListener('click',()=>voice.cancel());
}
try{state.pending=JSON.parse(sessionStorage.getItem('routine.pending')||'null')}catch{}
try{state.executionPending=JSON.parse(sessionStorage.getItem('execution.pending')||'null')}catch{}
const id=()=>crypto.randomUUID();
async function api(path,body,signal){const res=await fetch(path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json','X-Routine-App':'local','X-Routine-Language':locale()}:{'X-Routine-Language':locale()},body:body?JSON.stringify(body):undefined,signal});const data=await res.json();if(!res.ok)throw Object.assign(new Error(data.error.message),{code:data.error.code});return data;}
function message(text,kind='general'){const box=$('#message');box.textContent=text;box.dataset.kind=kind;if(text&&kind==='execution-connection'){const button=document.createElement('button');button.dataset.executionRefresh='';button.textContent=t('다시');box.append(button);}}
function clearConnectionMessage(){if($('#message').dataset.kind==='execution-connection')message('');}
function error(e){message(e.message||(t("연결을 확인하고 다시 시도해 주세요.")));if(state.pending){const b=document.createElement('button');b.textContent=(t("저장 결과 확인"));b.onclick=resolvePending;$('#message').append(b);}else if(e.code==='VERSION_CONFLICT'&&state.draft?.definitionId){const b=document.createElement('button');b.textContent=(t("최신 내용 보기"));b.onclick=async()=>{try{state.selected=await api('/api/routine?id='+encodeURIComponent(state.draft.definitionId));state.view='conflict-detail';render();}catch(e){error(e)}};$('#message').append(b);}}
async function load(){const [lib,cat,cap]=await Promise.all([api('/api/library'),api('/api/catalog'),api('/api/capabilities')]);state.metaEnabled=cap.meta;state.voiceEnabled=cap.voice;if(state.libraryRevision!==lib.revision)state.searchItems=null;state.libraryRevision=lib.revision;state.items=lib.items;state.catalog=cat.items.filter(r=>!r.lang||r.lang===locale());}
function card(r,kind){return `<button class="card" data-open="${escape(r.id)}" data-kind="${kind}"><strong>${escape(r.title)}</strong><small>${escape(t(r.author.name))} · ${stepCount(r.steps.length)}${r.source==='collected'?(" · "+t("추가한 루틴")):''}${r.generated?(" · "+t("새 제안")):''}${r.restMinutes?(" · "+t("휴식 {count}분",{count:r.restMinutes})):''}</small>${r.recommendationReason?`<span>${escape(r.recommendationReason)}</span>`:''}</button>`}
function render(){closeOptions();renderChrome();const c=$('#content');c.dataset.view=state.view;if(state.view==='step-detail'){renderStepDetail(c)}else if(state.view==='rest-plan'){renderRestPlan(c)}else if(state.view==='concurrent'){renderConcurrent(c)}else if(state.view==='find'){renderFind(c)}else if(state.view==='current'){renderCurrent(c)}else if(state.view==='run-detail'){renderRunDetail(c)}else if(state.view==='reservation-detail'){renderReservationDetail(c)}else if(state.view==='schedule'){renderSchedule(c)}else if(state.view==='add-choice'){renderAddChoice(c)}else if(state.view==='add-routine'){renderAddRoutine(c)}else if(state.view==='add-form'){renderAddForm(c)}else if(state.view==='add-google'){renderAddGoogle(c)}else if(state.view==='library'){c.innerHTML=`<div class="eyebrow">${t("나에게 맞는 작은 시작")}</div><div class="row between"><h1>${t("루틴 보관함")}</h1><button data-new aria-label="${t("루틴 만들기")}">＋</button></div><div class="filters">${[['all',(t("전체"))],['mine',(t("내가 만든"))],['collected',(t("추가한"))]].map(([v,t])=>`<button data-filter="${v}" aria-pressed="${state.filter===v}">${t}</button>`).join('')}</div>${state.items.filter(r=>state.filter==='all'||r.source===state.filter).map(r=>card(r,'library')).join('')||("<p class=\"empty\">"+t("나에게 필요한 루틴을 만들어 보세요.")+"<br>"+t("작은 행동 하나부터 시작해도 좋아요.")+"</p><button class=\"primary wide\" data-new>"+t("루틴 만들기")+"</button>")}`;}
else if(state.view==='catalog'){c.innerHTML=`<div class="eyebrow">${t("준비된 라이브러리")}</div><h1>${t("루틴 스토어")}</h1><p>${t("다른 사람이 만든 순서를 내 방식으로 가져오세요.")}</p>${state.catalog.map(r=>card(r,'catalog')).join('')}`;}
else if(['detail','preview','conflict-detail'].includes(state.view)){const r=state.view==='preview'?state.draft:state.selected;c.innerHTML=`<button data-back>‹ ${t("돌아가기")}</button><div class="orb" aria-hidden="true"></div><div class="eyebrow">${state.view==='preview'?(t("저장 전 미리보기")):escape(t(r.author.name))+' · '+stepCount(r.steps.length)}</div><h1>${escape(r.title)}</h1><p class="detail">${escape(r.description)}</p><ol>${r.steps.map(s=>`<li>${escape(s.title)}</li>`).join('')}</ol>${r.origin?`<p class="eyebrow">${t("원작: ")}${escape(t(r.origin.author.name))} · ${escape(r.origin.title)}</p>`:''}${r.generated?("<p class=\"eyebrow\">"+t("전체 단계를 확인한 뒤 시작하면 보관함에 추가됩니다.")+"</p>"):''}<div class="actions">${state.view==='preview'?("<button class=\"primary\" data-save>"+t("보관함에 저장")+"</button>"):state.view==='conflict-detail'?("<button data-back>"+t("내 초안으로")+"</button>"):state.selectedKind==='search'?("<button class=\"primary\" data-start>"+t("시작")+"</button>"):state.selectedKind==='catalog'?`<button class="primary" data-collect>${state.items.some(x=>x.origin?.id===r.id)?(t("보관함에서 보기")):(t("보관함에 추가"))}</button>`:("<button class=\"primary\" data-start>"+t("시작")+"</button><button data-schedule>"+t("예약")+"</button><button data-edit>"+t("편집")+"</button>")}</div>`;}
else if(state.view==='editor'){const d=state.draft;c.innerHTML=`<button data-back>‹ ${t("보관함")}</button><h1>${d.definitionId?(t("루틴 편집")):(t("루틴 만들기"))}</h1><form id="editor"><label for="title">${t("이름")}</label><input id="title" maxlength="200" value="${escape(d.title)}" required><label for="description">${t("설명")}</label><textarea id="description" maxlength="5000">${escape(d.description)}</textarea><label for="rest-minutes">${t("휴식 시간(분)")}</label><input id="rest-minutes" type="number" min="1" max="720" step="1" inputmode="numeric" placeholder="${t("휴식 루틴일 때만 입력")}" value="${escape(d.restMinutes??'')}"><label>${t("실행할 순서")}</label><div id="steps">${d.steps.map((s,i)=>`<div class="step"><input aria-label="${t('step.label',{count:i+1})}" data-step="${escape(s.id)}" value="${escape(s.title)}" maxlength="300" required><button type="button" data-remove="${escape(s.id)}" aria-label="${t('step.delete',{count:i+1})}">−</button><div class="step-reorder"><button type="button" data-move="${i}:-1" aria-label="${t('이전 단계로')}" ${i===0?'disabled':''}>↑</button><button type="button" data-move="${i}:1" aria-label="${t('다음 단계로')}" ${i===d.steps.length-1?'disabled':''}>↓</button></div></div>`).join('')}</div><button type="button" data-add>＋ ${t("step.add")}</button><div class="actions"><button type="button" data-draft>${t("초안 저장")}</button><button class="primary" type="submit">${t("전체 미리보기")}</button></div></form>`;}
if(state.pending)message((t("저장 결과 확인이 필요합니다. 아래 버튼으로 같은 요청을 확인해 주세요.")));if(state.pending)error(new Error($('#message').textContent));
decorateScreen();paintVoice();
$('#search-input')?.addEventListener('input',()=>{state.searchDraft=$('#search-input').value});
$('#search-form')?.addEventListener('submit',e=>{e.preventDefault();searchRoutines().catch(error)});
$('#editor')?.addEventListener('input',capture);
$('#editor')?.addEventListener('submit',async e=>{e.preventDefault();capture();await run(async()=>{await persistDraft();state.view='preview';render();message((t("초안을 저장했습니다. 전체 순서를 확인해 주세요.")));})});
}
function capture(){if(!$('#editor'))return;state.draft.title=$('#title').value;state.draft.description=$('#description').value;const rest=$('#rest-minutes').value;state.draft.restMinutes=rest?Number(rest):null;for(const s of state.draft.steps)s.title=document.querySelector(`[data-step="${CSS.escape(s.id)}"]`).value;}
async function persistDraft(){const r=await api('/api/drafts',{key:state.draftKey,expectedRevision:state.draftRevision,content:state.draft});state.draftRevision=r.revision;}
async function editor(r=null){state.detailReturn='library';state.draftKey=r?.id||'new';const saved=await api('/api/draft?key='+encodeURIComponent(state.draftKey));state.draftRevision=saved.revision;state.draft=saved.content?.steps?saved.content:{definitionId:r?.id||null,expectedVersion:r?.version||null,title:r?.title||'',description:r?.description||'',restMinutes:r?.restMinutes??null,steps:r?structuredClone(r.steps):[{id:id(),title:''}]};state.view='editor';render();message(saved.content?.steps?(t("저장된 초안을 불러왔습니다.")):'');}
async function navigate(view){state.browseId=null;state.showParent=false;state.dayBrowse=null;if(!state.pending&&!state.executionPending)message('');if(view!=='find'){cancelSearch();if(voiceBusy())voice.cancel();}capture();if(view==='current')await refreshExecution();if(state.draft&&['editor','preview','conflict-detail'].includes(state.view))await persistDraft();await load();state.view=view;if(view==='find'&&!state.searchQuery)state.findMode='home';render();window.scrollTo(0,0);if(view==='find'&&state.searchItems===null&&!state.searchDraft.trim())await searchRoutines();}
async function run(fn){if(state.busy)return;state.busy=true;document.querySelectorAll('button').forEach(b=>b.disabled=true);try{await fn()}catch(e){error(e)}finally{state.busy=false;document.querySelectorAll('button').forEach(b=>{b.disabled=b.hasAttribute('data-unavailable');if(b.dataset.move){const [i,d]=b.dataset.move.split(':').map(Number);b.disabled=i+d<0||i+d>=state.draft.steps.length;}});const language=$('#app-language');if(language)language.disabled=voiceBusy()||state.searchLoading;}}
async function commit(request){state.pending={request,draftKey:state.view==='preview'?state.draftKey:null,draftRevision:state.draftRevision};sessionStorage.setItem('routine.pending',JSON.stringify(state.pending));await sendPending();}
async function sendPending(){const result=await api('/api/commands',state.pending.request);await accept(result);}
async function accept(result){const pending=state.pending;
// Clear only the exact saved draft revision; a newer draft in another tab survives.
if(pending.draftKey){try{await api('/api/drafts',{key:pending.draftKey,expectedRevision:pending.draftRevision,content:{}})}catch{}}
state.pending=null;sessionStorage.removeItem('routine.pending');state.selected=result.routine;state.selectedKind='library';state.view='detail';render();message((t("보관함에 저장했습니다.")));try{await load()}catch{message((t("저장은 완료되었습니다. 목록 연결을 다시 확인해 주세요.")));}}
async function resolvePending(){await run(async()=>{try{await accept(await api('/api/command?id='+encodeURIComponent(state.pending.request.commandId)))}catch(e){if(e.code==='NOT_FOUND')await sendPending();else throw e;}})}
document.addEventListener('click',e=>{const b=e.target.closest('button');if(!b||b.hasAttribute('data-voice-main')||b.hasAttribute('data-voice-cancel')||state.busy||(b.form&&b.type==='submit'))return;run(async()=>{if(b.hasAttribute('data-execution-retry')){await sendExecution();return;}if(state.executionPending){executionMessage((t("먼저 실행 결과를 확인해 주세요.")));return;}if(state.pending){error(new Error((t("먼저 저장 결과를 확인해 주세요."))));return;}
if(b.hasAttribute('data-cancel-search')){cancelSearch();render();message((t("입력을 유지했습니다.")));}
else if(b.hasAttribute('data-search-more')){state.searchCount+=3;render();}
else if(b.hasAttribute('data-search-edit')){state.findMode='review';render();$('#search-input')?.focus();}
else if(b.hasAttribute('data-find-home')){state.findMode='home';render();}
else if(b.hasAttribute('data-show-parent')){state.showParent=true;state.browseId=null;state.dayBrowse=null;render();}
else if(b.dataset.dayPeer){const items=dayItems(),anchor=dayAnchor();state.turn=items.findIndex(x=>x.id===b.dataset.dayPeer)>items.findIndex(x=>x.id===(state.dayBrowse||anchor))?1:-1;state.dayBrowse=b.dataset.dayPeer===anchor?null:b.dataset.dayPeer;render();}
else if(b.hasAttribute('data-day-home')){state.dayBrowse=null;state.view='current';render();}
else if(b.dataset.dayOpen)openDayItem(b.dataset.dayOpen);
else if(b.hasAttribute('data-day-back')){state.view='current';render();}
else if(b.hasAttribute('data-child')){state.showParent=false;state.browseId=null;render();}
else if(b.dataset.resultFilter){state.resultFilter=b.dataset.resultFilter;state.resultIndex=0;render();}
else if(b.dataset.resultMove){moveResult(Number(b.dataset.resultMove));}
else if(b.hasAttribute('data-result-start')){state.selected=filteredSearch()[state.resultIndex];await beginSelected();}
else if(b.hasAttribute('data-step-detail')){state.stepIndex=Number(b.dataset.stepDetail);state.stepReturn=state.view;state.stepFromRun=state.view==='run-detail'||state.view==='current';if(state.view==='current')state.inspectRun=null;state.view='step-detail';render();}
else if(b.hasAttribute('data-step-back')){state.view=state.stepReturn||'detail';render();}
else if(b.dataset.inspectRun){state.inspectRun=b.dataset.inspectRun;state.view='run-detail';render();}
else if(b.hasAttribute('data-rest-apply'))await applyRestPlan();
else if(b.dataset.restEdit){state.restPlan.editing=state.restPlan.editing===b.dataset.restEdit?null:b.dataset.restEdit;render();}
else if(b.dataset.restChoice){const [rid,action]=b.dataset.restChoice.split(':');chooseRest(rid,action);await checkRest();}
else if(b.hasAttribute('data-rest-retry')){const p=state.restPlan;await previewRest(p.minutes,p.occurrenceId,true);}

else if(b.hasAttribute('data-together')){state.view='concurrent';render();}
else if(b.hasAttribute('data-start')){await beginSelected();}
else if(b.hasAttribute('data-options'))openOptions();
else if(b.dataset.peer){state.browseId=b.dataset.peer;render();}
else if(b.hasAttribute('data-return-current')){state.browseId=null;state.showParent=false;state.dayBrowse=null;state.inspectRun=null;state.view='current';render();}
else if(b.dataset.action)await executeAction(b.dataset.action);
else if(b.dataset.focus)await focusRun(b.dataset.focus);
else if(b.hasAttribute('data-execution-refresh')){await refreshExecution();state.view='current';render();}
else if(b.hasAttribute('data-run-detail')){state.inspectRun=null;state.view='run-detail';render();}
else if(b.hasAttribute('data-schedule')){state.view='schedule';render();}
else if(b.hasAttribute('data-reserve'))await reserveRoutine();
else if(b.hasAttribute('data-day-add')){await load();state.add=null;state.view='add-choice';render();}
else if(b.dataset.addKind){if(b.dataset.addKind==='schedule')openAdd('schedule');else if(b.dataset.addKind==='google')await openGoogle();else{state.view='add-routine';render();}}
else if(b.hasAttribute('data-google-import'))await importGoogle();
else if(b.dataset.addRoutine){const r=state.items.find(x=>x.id===b.dataset.addRoutine);if(r)openAdd('routine',r);}
else if(b.hasAttribute('data-schedule-save'))await saveAdd();
else if(b.hasAttribute('data-add-back')){state.view=state.view==='add-form'&&state.add?.kind==='routine'?'add-routine':'add-choice';state.add=null;render();}
else if(b.dataset.reservation)await startReservation(b.dataset.reservation);
else if(b.dataset.nav)await navigate(b.dataset.nav);
else if(b.hasAttribute('data-new'))await editor();
else if(b.dataset.filter){state.filter=b.dataset.filter;render()}
else if(b.dataset.open){state.selectedKind=b.dataset.kind;state.detailReturn=b.dataset.kind==='search'?'find':b.dataset.kind==='catalog'?'catalog':'library';state.selected=(b.dataset.kind==='search'?state.searchItems:b.dataset.kind==='catalog'?state.catalog:state.items).find(r=>r.id===b.dataset.open);state.view='detail';render();message('')}
else if(b.hasAttribute('data-edit'))await editor(state.selected);
else if(b.hasAttribute('data-back')){if(['preview','conflict-detail'].includes(state.view)){state.view='editor';render()}else await navigate(state.detailReturn||'library');}
else if(b.dataset.move){capture();const [index,delta]=b.dataset.move.split(':').map(Number);const next=index+delta;if(next>=0&&next<state.draft.steps.length){[state.draft.steps[index],state.draft.steps[next]]=[state.draft.steps[next],state.draft.steps[index]];}render();}
else if(b.hasAttribute('data-add')){capture();if(state.draft.steps.length<50)state.draft.steps.push({id:id(),title:''});render()}
else if(b.dataset.remove){capture();if(state.draft.steps.length>1)state.draft.steps=state.draft.steps.filter(s=>s.id!==b.dataset.remove);render()}
else if(b.hasAttribute('data-draft')){capture();await persistDraft();message((t("초안을 저장했습니다.")))}
else if(b.hasAttribute('data-save')){try{await commit({commandId:id(),kind:'saveDefinition',definitionId:state.draft.definitionId,expectedVersion:state.draft.expectedVersion,content:state.draft})}catch(e){if(e.code&&e.code!=='STORAGE_UNAVAILABLE'){state.pending=null;sessionStorage.removeItem('routine.pending')}throw e;}}
else if(b.hasAttribute('data-collect')){const existing=state.items.find(x=>x.origin?.id===state.selected.id);if(existing){state.selected=existing;state.selectedKind='library';render()}else await commit({commandId:id(),kind:'collectRoutine',sourceId:state.selected.id,sourceVersion:state.selected.version});}
})});
window.addEventListener('beforeunload',e=>{if(state.view==='editor'){e.preventDefault();e.returnValue=''}});


function executionMessage(text){message(text);if(state.executionPending){const b=document.createElement('button');b.textContent=(t("결과 확인"));b.dataset.executionRetry='';$('#message').append(b);}}
function applyExecution(next){const old=state.execution;const before=old?.workspace.runs.find(r=>r.id===old.workspace.focusId),after=next.workspace.runs.find(r=>r.id===next.workspace.focusId);if(before&&after&&before.id===after.id&&before.currentUnitId!==after.currentUnitId)state.turn=1;if(!old||next.workspace.revision>old.workspace.revision||(next.workspace.revision===old.workspace.revision&&next.serverNow>=old.serverNow))state.execution=next;}
async function refreshExecution(){applyExecution(await api('/api/execution/context'));clearConnectionMessage();}
function activeRun(){const w=state.execution?.workspace;return w?.runs.find(r=>r.id===w.focusId);}
function availableRun(r){return r.status==='running'&&(!r.definition.windowEndMillis||state.execution.serverNow<r.definition.windowEndMillis);}
function timeRange(start,end){return [start,end].map(v=>new Date(v).toLocaleTimeString(locale(),{hour:'2-digit',minute:'2-digit',hour12:false})).join('–');}
function renderCurrent(c){
 const ctx=state.execution;if(!ctx){c.innerHTML=`<h1>${t('현재 작업')}</h1><button data-execution-refresh>${t('불러오기')}</button>`;return;}
 const r=activeRun(),running=r&&availableRun(r),others=ctx.workspace.runs.filter(x=>availableRun(x)&&(!running||x.id!==r.id));
 if(running){const order=(r.order||r.steps.map(s=>s.id)).map(id=>r.steps.find(s=>s.id===id)).filter(Boolean),index=Math.max(0,order.findIndex(s=>s.id===(state.browseId||r.currentUnitId))),shown=order[index],browsing=state.browseId&&state.browseId!==r.currentUnitId,root=state.showParent;
 if(root||!order.length){renderDay(c,r.id,others);return;} // a plain schedule has no steps: its level is the day
 c.innerHTML=`<section class="focus-view">${orbitMarkup(r,order,index)}<div class="current-title"><button class="focus-title" ${root?'data-run-detail':`data-step-detail="${index}"`}><h1>${escape(root?r.definition.title:shown?.title||r.definition.title)}</h1></button><div class="row between focus-meta"><span>${t(browsing?'탐색 중':'진행 중')}${root?'':` · ${index+1} / ${order.length}`}${root&&r.definition.windowStartMillis?`<br>${timeRange(r.definition.windowStartMillis,r.definition.windowEndMillis)}`:''}</span>${others.length?`<button class="count-badge" data-together aria-label="${t('함께 진행 {count}',{count:others.length})}">+${others.length}</button>`:''}</div></div><div class="focus-footer">${browsing?`<button class="primary wide" data-return-current>${icon('back')} ${t('현재로')}</button>`:`<button class="primary wide" data-action="${root?'completeParent':'complete'}" ${root?'':'data-hold'}>${icon('check')} ${t('완료')}</button>`}</div></section>`;
 }else{const selection=ctx.reservation;
 if(selection.state==='none')c.innerHTML=`<section class="focus-view"><div class="current-title"><h1>${t('다음 작업 없음')}</h1><div class="row between focus-meta"><span></span><span class="day-tools">${others.length?`<button class="count-badge" data-together>+${others.length}</button>`:''}${addButton()}</span></div></div><div class="focus-footer"><button class="primary wide" data-nav="find">${icon('search')} ${t('루틴 찾기')}</button></div></section>`;
 else if(selection.state==='unavailable')c.innerHTML=`<h1>${t('일정을 확인할 수 없어요')}</h1><button data-execution-refresh>${t('다시')}</button>`;
 else if(selection.state==='conflict')c.innerHTML=`<h1>${t('겹치는 예약')}</h1>`+selection.candidates.map(x=>`<section class="card"><strong>${escape(x.title)}</strong><p>${timeRange(x.startMillis,x.endMillis)}</p><button data-reservation="${escape(x.id)}">${t('시작')}</button></section>`).join('');
 else renderDay(c,selection.candidates[0].id,others);}
}
// "My routine" (the whole day): today's runs and reservations in time order, one level above a routine's steps.
// Browsing here is preview only; Start / Focus here / Done stay the only state changes.
function dayItems(){const ctx=state.execution;if(!ctx)return [];if(Array.isArray(ctx.day))return ctx.day;
 // Older execution server without "day": running runs + the selected reservations only.
 const runs=ctx.workspace.runs.filter(availableRun).map(r=>{const order=r.order?.length?r.order:r.steps.map(s=>s.id);return {kind:'run',id:r.id,title:r.definition.title,atMillis:r.definition.windowStartMillis||ctx.serverNow,startMillis:r.definition.windowStartMillis,endMillis:r.definition.windowEndMillis,position:order.indexOf(r.currentUnitId)+1,total:order.length,definitionId:r.definition.id,definitionVersion:r.definition.version,occurrenceId:r.id};});
 const res=(ctx.reservation?.candidates||[]).map(x=>({kind:'reservation',id:x.id,title:x.title,atMillis:x.startMillis,startMillis:x.startMillis,endMillis:x.endMillis,position:0,total:0,definitionId:x.definitionId,definitionVersion:x.definitionVersion,occurrenceId:x.occurrenceId}));
 return [...runs,...res].sort((a,b)=>a.atMillis-b.atMillis||(a.kind==='run'?0:1)-(b.kind==='run'?0:1));}
function addButton(){return `<button class="day-add" data-day-add>＋ ${t('추가')}</button>`;}
function dayAnchor(){const r=activeRun();return r&&availableRun(r)?r.id:state.execution?.reservation?.state==='selected'?state.execution.reservation.candidates[0]?.id:null;}
function dayMeta(x){return googleTag(x.id)+(x.kind==='run'?`${t('진행 중')}${x.total?` · ${x.position||'–'} / ${x.total}`:x.startMillis?` · ${timeRange(x.startMillis,x.endMillis)}`:''}`:`${t('시작 전')} · ${timeRange(x.startMillis,x.endMillis)}`);}
function dayRunSteps(x){const r=state.execution?.workspace.runs.find(y=>y.id===x.id);if(!r)return [];return (r.order||r.steps.map(s=>s.id)).map(id=>r.steps.find(s=>s.id===id)).filter(Boolean);}
function renderDay(c,anchorId,others){const items=dayItems(),ctx=state.execution;let index=items.findIndex(x=>x.id===(state.dayBrowse||anchorId));if(index<0){state.dayBrowse=null;index=Math.max(0,items.findIndex(x=>x.id===anchorId));}
 const x=items[index];if(!x){c.innerHTML=`<section class="focus-view"><div class="current-title"><h1>${t('다음 작업 없음')}</h1><div class="row between focus-meta"><span></span><span class="day-tools">${addButton()}</span></div></div></section>`;return;}
 const browsing=x.id!==anchorId,anchorRun=ctx.workspace.runs.find(r=>r.id===anchorId&&availableRun(r)),early=x.kind==='reservation'&&ctx.serverNow<x.startMillis;
 const cta=browsing?`<button class="primary wide" data-day-home>${icon('back')} ${t('현재로')}</button>`:anchorRun?`<button class="primary wide" data-action="completeParent">${icon('check')} ${t('완료')}</button>`:`<button class="primary wide" data-reservation="${escape(x.id)}" ${early?'data-unavailable disabled':''}>${t('시작')}</button>${early?`<p class="schedule-caption">${t('예약된 시각에 시작할 수 있어요')}</p>`:''}`;
 c.innerHTML=`<section class="focus-view day-view">${dayOrbit(items,index)}<div class="current-title"><button class="focus-title" data-day-open="${escape(x.id)}"><h1>${escape(x.title)}</h1></button><div class="row between focus-meta"><span>${browsing?`${t('탐색 중')} · `:''}${dayMeta(x)}</span><span class="day-tools">${others.length?`<button class="count-badge" data-together aria-label="${t('함께 진행 {count}',{count:others.length})}">+${others.length}</button>`:''}${addButton()}</span></div></div><div class="focus-footer">${cta}</div></section>`;}
function dayOrbit(items,index){const {w,h,r:radius,cy}=stageSize(),x=items[index],slots=clockSlots(),slot=id=>slots.find(s=>s.id===id),anchor=dayAnchor();
 const current=slots.find(s=>s.role==='current');
 const nodes=items.filter(item=>!(current&&item.id===current.id)).map(item=>({at:slot(item.id)?.atMillis??item.atMillis,cls:item.kind==='run'?'day-run':'day-reservation',selected:item.id===x.id&&item.id!==anchor}));
 const timer=current?{start:current.startMillis,end:current.endMillis}:null,showWindow=!current||x.id!==current.id;
 const steps=x.kind==='run'?dayRunSteps(x):[];
 const ring=steps.length?`<circle cx="${radius}" cy="${cy}" r="34" class="satellite-orbit"/>`+steps.slice(0,3).map((step,i)=>{const a=(-100+i*100)*Math.PI/180;return `<circle cx="${radius+34*Math.cos(a)}" cy="${cy+34*Math.sin(a)}" r="4" class="${step.status==='completed'?'root-done':'root-pending'}"/>`;}).join(''):'';
 return `<div class="orbit-scene day-scene" tabindex="0" aria-label="${t('궤도 탐색')}"><svg viewBox="0 0 ${w} ${h}" aria-hidden="true"><circle class="parent-core" cx="0" cy="${cy}" r="24"/>${windowOrbit(showWindow?x.startMillis:current.startMillis,showWindow?x.endMillis:current.endMillis,{h,r:radius,cy},steps.length>0,'day',{nodes,timer:showWindow?null:timer})}${ring}<circle cx="${radius}" cy="${cy}" r="18" fill="white"/><circle class="planet" cx="${radius}" cy="${cy}" r="14"/></svg><button class="orbit-parent" data-day-home>${t('나의 루틴')}</button>${items.map((item,i)=>{const d=i-index;if(Math.abs(d)>1)return '';return `<button class="orbit-hit orbit-position-${d+1}" ${d===0?`data-day-open="${escape(item.id)}"`:`data-day-peer="${escape(item.id)}"`} aria-label="${escape(item.title)}"></button>`;}).join('')}</div>`;}
// Going down from the day level: the focused run -> its steps; another run -> its detail (Focus here); a reservation -> its detail (Start).
function openDayItem(key){const x=dayItems().find(y=>y.id===key);if(!x)return;const focused=activeRun();
 if(x.kind==='run'&&focused&&x.id===focused.id&&availableRun(focused)){state.showParent=false;state.dayBrowse=null;state.browseId=null;render();return;}
 if(x.kind==='run'){state.inspectRun=x.id;state.view='run-detail';render();return;}
 state.dayReservation=x;state.view='reservation-detail';render();}
function renderReservationDetail(c){const x=state.dayReservation,ctx=state.execution;if(!x||!ctx){state.view='current';renderCurrent(c);return;}const r=state.items.find(y=>y.id===x.definitionId),open=ctx.serverNow>=x.startMillis&&ctx.serverNow<x.endMillis;
 c.innerHTML=`<h1>${escape(x.title)}</h1>${googleTag(x.id)}<span class="pill">${x.plain?`${t('일정')} · `:''}${t('시작 전')} · ${timeRange(x.startMillis,x.endMillis)}</span>${r?.description?`<div class="label-small">${t('목적')}</div><p class="detail">${escape(r.description)}</p>`:''}${r?`<div class="label-small">${t('전체 단계')} · ${r.steps.length}</div><ol class="routine-steps">${r.steps.map((s,i)=>`<li><button disabled data-unavailable><span class="step-number">${i+1}</span><span>${escape(s.title)}</span></button></li>`).join('')}</ol>`:''}<div class="actions"><button class="primary" data-reservation="${escape(x.id)}" ${open?'':'data-unavailable disabled'}>${t('시작')}</button>${open?'':`<p class="schedule-caption">${t('예약된 시각에 시작할 수 있어요')}</p>`}<button data-day-back>${t('돌아가기')}</button></div>`;}
function runForDetail(){return state.execution?.workspace.runs.find(r=>r.id===state.inspectRun)||activeRun();}
function stepRows(steps){return `<div class="label-small">${t('전체 단계')} · ${steps.length}</div><ol class="routine-steps">${steps.map((s,i)=>`<li><button data-step-detail="${i}"><span class="step-number ${s.status==='completed'?'done':''}">${s.status==='completed'?icon('check'):i+1}</span><span>${escape(s.title)}</span>${icon('chev')}</button></li>`).join('')}</ol>`;}
function renderRunDetail(c){const r=runForDetail();if(!r){state.view='current';renderCurrent(c);return;}const steps=(r.order||r.steps.map(s=>s.id)).map(id=>r.steps.find(s=>s.id===id)).filter(Boolean);c.innerHTML=`<h1>${escape(r.definition.title)}</h1><span class="pill">${escape(t(r.definition.author))}</span>${r.definition.description?`<div class="label-small">${t('목적')}</div><p class="detail">${escape(r.definition.description)}</p>`:''}${stepRows(steps)}<div class="actions"><button class="primary" ${r.id===activeRun()?.id?'data-return-current':`data-focus="${escape(r.id)}"`}>${t(r.id===activeRun()?.id?'현재로':'집중하기')}</button>${availableRun(r)&&r.id===activeRun()?.id?`<button class="text-button" data-action="completeParent">${t('루틴 전체 완료')}</button>`:''}</div>`;}
function renderStepDetail(c){const r=state.stepFromRun?runForDetail():state.stepReturn==='preview'?state.draft:state.selected;const steps=state.stepFromRun?(r.order||r.steps.map(s=>s.id)).map(id=>r.steps.find(s=>s.id===id)):r.steps;const step=steps[state.stepIndex];c.innerHTML=`<h1>${escape(step.title)}</h1><span class="pill">${escape(t(state.stepFromRun?r.definition.author:r.author?.name||''))}</span>${step.description?`<div class="label-small">${t('작업 안내')}</div><p class="detail">${escape(step.description)}</p>`:''}<button class="card" data-step-back><strong>${escape(state.stepFromRun?r.definition.title:r.title)}</strong>${icon('chev')}</button><div class="actions"><button class="primary" ${state.stepFromRun?'data-return-current':state.stepReturn==='preview'?'data-step-back':'data-start'}>${t(state.stepFromRun?'현재로':state.stepReturn==='preview'?'전체 미리보기':'시작')}</button></div>`;}
function renderConcurrent(c){const list=state.execution?.workspace.runs.filter(availableRun)||[];c.innerHTML=`<h1>${t('함께 진행 중')}</h1>${list.map(r=>`<button class="card" data-inspect-run="${escape(r.id)}"><strong>${escape(r.definition.title)}</strong><small>${t(r.id===activeRun()?.id?'현재 작업':'진행 중')}</small>${icon('chev')}</button>`).join('')}`;}
async function beginSelected(){if(state.selected.generated)await commit({commandId:id(),kind:'acceptGenerated',proposalId:state.selected.id});const existing=state.execution?.workspace.runs.find(r=>availableRun(r)&&r.definition.id===state.selected.id);if(existing)await focusRun(existing.id);else{const r=state.selected,occurrence=id();await startRoutine(r,occurrence);if(r.restMinutes&&state.execution?.workspace.runs.some(x=>x.id===occurrence&&availableRun(x)))await previewRest(r.restMinutes,occurrence);}}
// Starting a rest routine opens the change summary with the AI batch proposal already inside.
// Nothing changes until the single Apply. Choosing nothing applies the proposal as shown.
async function previewRest(minutes,occurrenceId,retryAi=false){state.restPlan={loading:true,minutes,occurrenceId};state.view='rest-plan';render();
 let out;try{out=await api('/api/rest/proposal',{occurrenceId,restMinutes:minutes,language:locale(),...(retryAi?{retryAi:true}:{})});}catch(e){state.restPlan=null;state.view='current';render();throw e;}
 if(!out.proposal.items.length){state.restPlan=null;state.view='current';render();message(t('휴식 시간과 겹치는 일정이 없어요.'));return;}
 state.restPlan={minutes,occurrenceId,proposal:out.proposal,ai:out.ai,choices:{},editing:null,issues:[],applyId:id(),applied:false};state.view='rest-plan';render();}
function restDecisions(){const p=state.restPlan;return p.proposal.items.map(i=>p.choices[i.reservation.id]||i.proposed);}
function restBody(dryRun=false){const p=state.restPlan;return {id:dryRun?id():p.applyId,occurrenceId:p.occurrenceId,restMinutes:p.minutes,expectedRevision:p.proposal.expectedRevision,decisions:restDecisions(),...(dryRun?{dryRun:true}:{})};}
async function checkRest(){const p=state.restPlan;const out=await api('/api/execution/reschedule/apply',restBody(true));p.issues=out.issues||[];if(out.reason==='STALE_REVISION')message(t('일정이 그사이 바뀌어 적용하지 않았어요. 다시 확인해 주세요.'));render();}
async function applyRestPlan(){const p=state.restPlan;if(!p||p.applied||p.loading)return;const out=await api('/api/execution/reschedule/apply',restBody());
 if(!out.accepted){p.issues=out.issues||[];p.applyId=id();render();message(t(out.reason==='INVALID_DECISIONS'?'확인이 필요한 항목이 있어 적용하지 않았어요.':'일정이 그사이 바뀌어 적용하지 않았어요. 다시 확인해 주세요.'));return;}
 p.applied=true;p.reservations=out.reservations;await refreshExecution();render();}
function chooseRest(id,action){const p=state.restPlan,item=p.proposal.items.find(i=>i.reservation.id===id);if(!item)return;
 if(action==='proposed')delete p.choices[id];
 else if(action==='move'){const prev=p.choices[id]?.action==='move'?p.choices[id]:null;const start=prev?.newStartMillis??(item.proposed.action==='move'?item.proposed.newStartMillis:item.alternative.action==='move'?item.alternative.newStartMillis:p.proposal.restEndMillis);p.choices[id]={reservationId:id,action:'move',newStartMillis:start,source:'user'};}
 else p.choices[id]={reservationId:id,action,source:'user'};}
function clock(v){return new Date(v).toLocaleTimeString(locale(),{hour:'2-digit',minute:'2-digit',hour12:false});}
const restActionLabel={move:'다른 시간으로 미루기',skip_this_time:'이번에는 안 함',keep:'그대로 두기',later:'나중에 직접 정하기'};
const restIssueLabel={PAST_DAY_END:'하루 마감 이후',PAST_DEADLINE:'마감 이후',OVERLAP:'다른 일정과 겹침',INSIDE_REST_WINDOW:'휴식 시간 안',REQUIRED_FIXED:'필수 일정은 그대로',NOT_MOVABLE:'시간 변경 불가',MISSING_TIME:'시간 없음',BAD_ACTION:'알 수 없는 처리',MISSING:'AI 제안 없음',DUPLICATE:'중복 제안',UNKNOWN_ID:'알 수 없는 일정',NOT_AFFECTED:'휴식 시간 밖 일정'};
const restReasonLabel={EARLIEST_FREE:'휴식 뒤 가장 빠른 빈 시간',DOES_NOT_FIT_DAY_END:'하루 마감 전에 맞는 시간이 없어요',DOES_NOT_FIT_DEADLINE:'마감 전에 맞는 시간이 없어요',REQUIRED:'필수 일정',NOT_MOVABLE:'시간 변경 불가'};
function restOutcome(r,d){const len=r.endMillis-r.startMillis;if(d.action==='move')return `<b>${timeRange(d.newStartMillis,d.newStartMillis+len)}</b>`;if(d.action==='keep')return `<b>${t(r.required?'필수 일정 — 그대로':'그대로 두기')}</b>`;if(d.action==='skip_this_time')return `<b class="cancelled">${t('이번에는 안 함')}</b><small>${t('앱 안에서만 표시해요. 외부 일정은 취소하지 않아요.')}</small>`;return `<b>${t('나중에 직접 정하기')}</b><small>${t('시간을 정하지 않고 재조율 목록에 남겨요.')}</small>`;}
function restReason(d){return d.source==='ai'&&d.reason?escape(d.reason):d.reason&&restReasonLabel[d.reason]?t(restReasonLabel[d.reason]):'';}
function restRow(i){const p=state.restPlan,r=i.reservation,choice=p.choices[r.id],d=choice||i.proposed,issues=p.issues.filter(x=>x.reservationId===r.id);
 const needsCheck=i.ai&&i.aiIssues.length;const len=r.endMillis-r.startMillis;
 const aiNote=needsCheck&&!p.applied?`<p class="rest-check"><span class="pill warn">${t('확인 필요')}</span> ${t('AI 제안')}: <s>${i.ai.action==='move'&&i.ai.newStartMillis!=null?timeRange(i.ai.newStartMillis,i.ai.newStartMillis+len):t(restActionLabel[i.ai.action]||'알 수 없는 처리')}</s> — ${i.aiIssues.map(c=>t(restIssueLabel[c]||c)).join(', ')}. ${t('대신 규칙 기반 대안을 넣었어요.')}</p>`:'';
 const editing=p.editing===r.id&&!p.applied;const fixed=i.allowed.length===1;
 const options=editing?`<div class="rest-options" role="radiogroup" aria-label="${t('처리 바꾸기')}">${[['proposed',t(p.proposal.source==='ai'?'AI 제안대로':'조정안대로')],...i.allowed.map(a=>[a,t(restActionLabel[a])])].map(([a,label])=>`<button type="button" role="radio" aria-checked="${a==='proposed'?!choice:choice?.action===a}" data-rest-choice="${escape(r.id)}:${a}">${label}</button>`).join('')}${choice?.action==='move'?`<label for="rest-time-${escape(r.id)}">${t('새 시작 시각')}</label><input id="rest-time-${escape(r.id)}" type="time" step="300" data-rest-time="${escape(r.id)}" value="${clock(choice.newStartMillis)}">`:''}</div>`:'';
 return `<li class="reschedule-item${issues.length?' has-issue':''}"><strong>${escape(r.title)}${r.required?` <span class="pill">${t('필수')}</span>`:''}${googleTag(r.id)?` ${googleTag(r.id)}`:''}${choice?` <span class="pill">${t('내가 바꿈')}</span>`:''}</strong><span>${d.action==='keep'?`${timeRange(r.startMillis,r.endMillis)} · `:`<s>${timeRange(r.startMillis,r.endMillis)}</s> → `}${restOutcome(r,d)}</span>${restReason(d)?`<small>${restReason(d)}</small>`:''}${aiNote}${issues.length?`<p class="rest-issue">${t('적용할 수 없어요')}: ${issues.map(x=>t(restIssueLabel[x.code]||x.code)).join(', ')}</p>`:''}${!fixed&&!p.applied?`<button class="text-button" data-rest-edit="${escape(r.id)}" aria-expanded="${editing}">${t(editing?'닫기':'바꾸기')}</button>`:''}${options}</li>`;}
function renderRestPlan(c){const p=state.restPlan;if(!p){state.view='current';renderCurrent(c);return;}
 if(p.loading){c.innerHTML=`<span class="pill">${t('일정 조정안')}</span><h1>${t('휴식하는 동안의 일정을 정리하고 있어요')}</h1><p class="muted">${t('AI 조정안을 만드는 중이에요. 아무것도 바꾸지 않았어요.')}</p>`;return;}
 const plan=p.proposal,now=state.execution?.serverNow||0;
 const source=p.ai.status==='ok'?`<span class="pill">${t('AI 조정안')}</span>`:`<span class="pill">${t('규칙 기반 제안')}</span><p class="muted">${t(p.ai.status==='off'?'AI 연결이 꺼져 있어 규칙 기반 제안을 보여줘요.':'AI 조정안을 받지 못해 규칙 기반 제안을 보여줘요. 입력과 일정은 그대로예요.')}</p>${p.ai.status==='error'&&!p.applied?`<button class="text-button" data-rest-retry>${t('AI 조정안 다시 받기')}</button>`:''}`;
 const rows=plan.items.map(restRow).join('');
 const active=(p.reservations||[]).filter(x=>!x.status&&x.endMillis>now).sort((a,b)=>a.startMillis-b.startMillis),later=(p.reservations||[]).filter(x=>x.status==='unscheduled'),skipped=(p.reservations||[]).filter(x=>x.status==='skipped');
 const list=(items,f)=>`<ul class="reschedule-list">${items.map(x=>`<li class="reschedule-item"><strong>${escape(x.title)}</strong><span>${f(x)}</span></li>`).join('')}</ul>`;
 const after=p.applied?`${active.length?`<div class="label-small">${t('오늘 남은 일정')}</div>${list(active,x=>timeRange(x.startMillis,x.endMillis))}`:''}${later.length?`<div class="label-small">${t('나중에 정할 일')}</div>${list(later,()=>t('시간 미정'))}`:''}${skipped.length?`<div class="label-small">${t('이번에는 안 함')}</div>${list(skipped,()=>t('앱 안에서만 표시해요. 외부 일정은 취소하지 않아요.'))}`:''}`:'';
 c.innerHTML=`${p.applied?`<span class="pill">${t('적용했어요')}</span>`:source}<h1>${t(p.applied?'바뀐 일정':'휴식하는 동안의 일정 조정안')}</h1><p class="muted">${t('휴식 {range}',{range:timeRange(plan.restStartMillis,plan.restEndMillis)})} · ${t('필수 일정은 그대로예요.')}</p>${p.applied?'':`<p class="schedule-caption">${t('조정안이 기본이에요. 바꾸고 싶은 항목만 고르세요. 아무것도 고르지 않으면 조정안 그대로 적용돼요.')}</p>`}<ul class="reschedule-list">${rows}</ul>${after}${p.applied?'':`<p class="schedule-caption">${t('적용을 누르기 전에는 아무것도 바뀌지 않아요.')}</p>`}<div class="actions">${p.applied?`<button class="primary" data-return-current>${t('현재로')}</button>`:`<button class="primary" data-rest-apply>${t('한 번에 적용')}</button>`}</div>`;
 c.querySelectorAll('[data-rest-time]').forEach(input=>input.addEventListener('change',()=>{const ch=p.choices[input.dataset.restTime];const [h,m]=input.value.split(':').map(Number);if(!ch||!Number.isFinite(h))return;const d=new Date(plan.restStartMillis);d.setHours(h,m,0,0);ch.newStartMillis=d.getTime();run(checkRest);}));}
async function submitExecution(command){state.executionPending=command;sessionStorage.setItem('execution.pending',JSON.stringify(command));await sendExecution();}
async function sendExecution(){try{const completedAction=['complete','completeParent'].includes(state.executionPending?.kind);const out=await api('/api/execution/command',state.executionPending);state.executionPending=null;sessionStorage.removeItem('execution.pending');applyExecution(out.context);state.view='current';state.showParent=false;render();const reasons={NO_NEXT_UNIT:(t("다음 단계가 없어 미룰 수 없어요.")),WINDOW_ELAPSED:(t("다음 예약을 확인해 주세요.")),STALE_REVISION:(t("다른 화면에서 변경되었습니다. 현재 내용을 확인해 주세요.")),FOCUS_CHANGED:(t("집중하는 작업이 바뀌었습니다. 다시 확인해 주세요."))};message(out.result.accepted?'':reasons[out.result.reason]||(t("현재 상태에서는 실행할 수 없어요.")));if(out.result.accepted&&completedAction)completionToast();}catch(e){executionMessage(e.message);}}
async function startRoutine(r,occurrenceId=id()){await refreshExecution();await submitExecution({id:id(),kind:'start',occurrenceId,expectedRevision:state.execution.workspace.revision,definition:{id:r.id,version:r.version,title:r.title,author:r.author?.name||'',description:r.description||'',steps:r.steps||[]}});}
async function executeAction(kind){state.browseId=null;if(state.showParent&&kind==='complete')kind='completeParent';if(state.showParent&&['defer','skip'].includes(kind))return;const w=state.execution.workspace,r=activeRun();if(!r)return;await submitExecution({id:id(),kind,occurrenceId:r.id,expectedRevision:r.revision,unitId:kind==='completeParent'?null:r.currentUnitId,expectedFocusRevision:w.focusRevision});}
async function focusRun(occurrenceId){await submitExecution({id:id(),kind:'focus',occurrenceId,expectedRevision:state.execution.workspace.revision});}
async function startReservation(key){const item=state.execution.reservation.candidates.find(x=>x.id===key)||dayItems().find(x=>x.kind==='reservation'&&x.id===key);if(!item)return;await startRoutine({id:item.definitionId,version:item.definitionVersion,title:item.title},item.occurrenceId);}
function renderSchedule(c){c.innerHTML=`<button data-back>‹ ${t("보관함")}</button><h1>${escape(state.selected.title)}</h1><label for="reservation-start">${t("시작")}</label><input id="reservation-start" type="datetime-local"><label for="reservation-end">${t("종료")}</label><input id="reservation-end" type="datetime-local"><label class="check"><input id="reservation-required" type="checkbox"> ${t("필수")}</label><label class="check"><input id="reservation-movable" type="checkbox" checked> ${t("시간 변경 가능")}</label><label for="reservation-deadline">${t("마감 (선택)")}</label><input id="reservation-deadline" type="datetime-local"><div class="actions"><button class="primary" data-reserve>${t("예약")}</button></div>`;}
async function reserveRoutine(){const startMillis=new Date($('#reservation-start').value).getTime(),endMillis=new Date($('#reservation-end').value).getTime();if(!Number.isFinite(startMillis)||!Number.isFinite(endMillis)||endMillis<=startMillis){message((t("시작과 종료 시각을 확인해 주세요.")));return;}const deadlineText=$('#reservation-deadline').value,deadlineMillis=deadlineText?new Date(deadlineText).getTime():null;if(deadlineMillis!==null&&!(deadlineMillis>=endMillis)){message(t("마감은 종료 시각 이후로 정해 주세요."));return;}const required=$('#reservation-required').checked;const key=state.reservationKey||(state.reservationKey=id());await api('/api/execution/reservations',{id:key,definitionId:state.selected.id,definitionVersion:state.selected.version,title:state.selected.title,startMillis,endMillis,required,movable:required?false:$('#reservation-movable').checked,deadlineMillis});state.reservationKey=null;await refreshExecution();state.view='current';render();message((t("예약했습니다. 자동으로 시작하지 않습니다.")));}

// "+ Add" at the day level (2026-11-04 user decision): a plain schedule (no steps) or a saved routine, always start–end.
// Times are today's (server clock). Nothing starts by itself; the reservation id is reused for a retry of the same request.
function serverDay(){return new Date(state.execution?.serverNow||Date.now());}
function hhmm(ms){const d=new Date(ms);return String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0');}
function todayAt(value){const m=/^(\d{2}):(\d{2})$/.exec(value||'');if(!m)return NaN;const d=serverDay();d.setHours(+m[1],+m[2],0,0);return d.getTime();}
function openAdd(kind,routine=null){const d=serverDay();d.setMinutes(d.getMinutes()<30?30:60,0,0);const start=d.getTime(),end=Math.min(start+30*60000,new Date(d).setHours(23,59,0,0));
 state.add={kind,routine,start:hhmm(start),end:hhmm(end)};state.view='add-form';render();$(kind==='schedule'?'#schedule-title':'#schedule-start')?.focus();}
function renderAddChoice(c){c.innerHTML=`<h1>${t('나의 루틴에 추가')}</h1><button class="card add-kind" data-add-kind="schedule"><strong>${t('일정')}</strong><small>${t('시간만 정한 계획이에요. 단계는 없어요.')}</small>${icon('chev')}</button><button class="card add-kind" data-add-kind="routine"><strong>${t('루틴')}</strong><small>${t('저장한 루틴을 정한 시간에 해요.')}</small>${icon('chev')}</button><button class="card add-kind" data-add-kind="google"><strong>${t('구글 캘린더')}</strong><small>${t('오늘 일정을 필수 일정으로 가져와요. 읽기만 해요.')}</small>${icon('chev')}</button>`;}
function renderAddRoutine(c){c.innerHTML=`<h1>${t('루틴 고르기')}</h1>${state.items.map(r=>`<button class="card add-kind" data-add-routine="${escape(r.id)}"><strong>${escape(r.title)}</strong><small>${escape(stepCount(r.steps.length))}</small>${icon('chev')}</button>`).join('')||`<p class="empty">${t('보관함에 루틴이 없어요.')}</p>`}`;}
function renderAddForm(c){const a=state.add,date=serverDay().toLocaleDateString(locale(),{weekday:'short',month:'short',day:'numeric'});
 c.innerHTML=`<h1>${a.kind==='schedule'?t('새 일정'):escape(a.routine.title)}</h1><span class="pill">${a.kind==='schedule'?t('일정'):t('루틴')} · ${t('오늘 {date}',{date})}</span><form id="add-form" novalidate>${a.kind==='schedule'?`<label for="schedule-title">${t('제목')}</label><input id="schedule-title" maxlength="120" autocomplete="off" required>`:''}<div class="time-pair"><div><label for="schedule-start">${t('시작')}</label><input id="schedule-start" type="time" required value="${a.start}"></div><div><label for="schedule-end">${t('종료')}</label><input id="schedule-end" type="time" required value="${a.end}"></div></div><p id="schedule-error" class="form-error" role="alert" hidden></p><label class="check"><input id="schedule-required" type="checkbox"> ${t('필수')}</label><label class="check"><input id="schedule-movable" type="checkbox" checked> ${t('시간 변경 가능')}</label><label for="schedule-deadline">${t('마감 (선택)')}</label><input id="schedule-deadline" type="time"></form><div class="actions"><button class="primary" data-schedule-save>${t('저장')}</button></div>`;
 const required=$('#schedule-required'),movable=$('#schedule-movable');required.onchange=()=>{movable.disabled=required.checked;if(required.checked)movable.checked=false;};
 c.querySelectorAll('#add-form input').forEach(i=>i.addEventListener('input',()=>{const e=$('#schedule-error');if(e)e.hidden=true;}));
 $('#add-form').onsubmit=e=>{e.preventDefault();run(saveAdd);};}
function addError(text){const e=$('#schedule-error');e.textContent=text;e.hidden=false;}
async function saveAdd(){const a=state.add;if(!a)return;const title=a.kind==='schedule'?$('#schedule-title').value.trim():a.routine.title;
 const startMillis=todayAt($('#schedule-start').value),endMillis=todayAt($('#schedule-end').value),deadlineText=$('#schedule-deadline').value,deadlineMillis=deadlineText?todayAt(deadlineText):null;
 if(!title){addError(t('제목을 입력해 주세요.'));$('#schedule-title').focus();return;}
 if(!Number.isFinite(startMillis)||!Number.isFinite(endMillis)||endMillis<=startMillis){addError(t('종료 시각은 시작 시각보다 늦어야 해요.'));$('#schedule-end').focus();return;}
 if(endMillis<=(state.execution?.serverNow||Date.now())){addError(t('종료 시각이 이미 지났어요.'));return;}
 if(deadlineMillis!==null&&!(deadlineMillis>=endMillis)){addError(t('마감은 종료 시각 이후로 정해 주세요.'));return;}
 const required=$('#schedule-required').checked,body={kind:a.kind,definitionId:a.kind==='schedule'?'schedule':a.routine.id,definitionVersion:a.kind==='schedule'?1:a.routine.version,title,startMillis,endMillis,required,movable:required?false:$('#schedule-movable').checked,deadlineMillis};
 const fingerprint=JSON.stringify(body);if(a.fingerprint!==fingerprint){a.fingerprint=fingerprint;a.key=id();}
 await api('/api/execution/reservations',{id:a.key,...body});state.add=null;await refreshExecution();
 const r=activeRun();state.view='current';state.showParent=!!(r&&availableRun(r));state.browseId=null;state.dayBrowse=a.key===dayAnchor()?null:dayItems().some(x=>x.id===a.key)?a.key:null;render();message('');toast(t('나의 루틴에 추가했어요'),2600);} // a toast, so the new item's title stays visible

// Google Calendar (read-only): the secret iCal address goes to this local app only; today's timed events become Required plans.
// The server keeps the address in the local data dir and never returns it. Imported plans have ids "gcal-…" (the Google tag).
function googleTag(key){return /(^|-)gcal-/.test(key||'')?`<span class="pill tag-google">Google</span>`:'';}
async function openGoogle(){state.googleSaved=false;try{state.googleSaved=(await api('/api/calendar/google')).saved;}catch{}state.view='add-google';render();$('#google-url')?.focus();}
function renderAddGoogle(c){const date=serverDay().toLocaleDateString(locale(),{weekday:'short',month:'short',day:'numeric'});
 c.innerHTML=`<h1>${t('구글 캘린더')}</h1><span class="pill">${t('오늘 {date}',{date})}</span><p class="schedule-caption">${t('오늘 일정을 필수 일정으로 가져와요. 읽기만 해요.')}</p><form id="google-form" novalidate><label for="google-url">${t('iCal 형식의 비밀 주소')}</label><input id="google-url" type="url" inputmode="url" autocomplete="off" autocapitalize="off" spellcheck="false" placeholder="https://calendar.google.com/calendar/ical/…/basic.ics"><p class="schedule-caption">${t('구글 캘린더 → 설정 → 내 캘린더 → iCal 형식의 비밀 주소')}</p>${state.googleSaved?`<p class="schedule-caption">${t('저장된 주소가 있어요. 비워 두면 그 주소로 가져와요.')}</p>`:''}<p id="google-error" class="form-error" role="alert" hidden></p></form><div class="actions"><button class="primary" data-google-import>${t('가져오기')}</button></div>`;
 $('#google-url').addEventListener('input',()=>{$('#google-error').hidden=true;});$('#google-form').onsubmit=e=>{e.preventDefault();run(importGoogle);};}
function googleError(text){const e=$('#google-error');e.textContent=text;e.hidden=false;}
async function importGoogle(){const url=$('#google-url').value.trim();if(!url&&!state.googleSaved){googleError(t('iCal 주소를 확인해 주세요.'));$('#google-url').focus();return;}
 let out;try{out=await api('/api/calendar/google/import',{url});}catch(e){googleError(e.message);return;}
 $('#google-url').value='';await refreshExecution();const first=out.ids.find(k=>dayItems().some(x=>x.id===k)),r=activeRun();
 state.view='current';state.showParent=!!(r&&availableRun(r));state.browseId=null;state.dayBrowse=first&&first!==dayAnchor()?first:null;render();message('');
 const n=out.added,parts=[out.added||!out.unchanged?t(n===1?'google.added.one':'google.added.other',{count:n}):'',out.unchanged?t('이미 있는 일정 {count}개',{count:out.unchanged}):'',out.changed?t('구글에서 바뀐 일정 {count}개는 아직 반영하지 않았어요',{count:out.changed}):'',out.allDay?t('종일 일정 {count}개는 넣지 않았어요',{count:out.allDay}):''];
 toast(parts.filter(Boolean).join(' · '),3600);}

// Read-only refresh advances reservation display; it never issues a start or completion.
setInterval(async()=>{if(state.view!=='current'||state.busy||state.executionPending||optionLayer||document.hidden)return;try{const before=executionKey();await refreshExecution();if(state.view==='current'&&!state.busy&&before!==executionKey())render();}catch{message((t("연결을 확인해 주세요. 표시된 작업은 마지막 확인 상태입니다.")),'execution-connection');}},5000);

function toast(text,ms=1600){document.querySelector('.completion-toast')?.remove();const e=document.createElement('div');e.className='completion-toast';e.setAttribute('role','status');e.textContent=text;document.body.append(e);setTimeout(()=>e.remove(),ms);}
function completionToast(){toast('✓ '+t('완료'));}
function executionKey(){const c=state.execution;return JSON.stringify(c&&{workspace:c.workspace,reservation:c.reservation,timeFrame:c.orbit?Math.floor(c.serverNow/60000):c.workspace.runs.some(r=>r.definition.windowStartMillis)||c.reservation?.candidates?.length?Math.floor(c.serverNow/5000):null,active:c.workspace.runs.map(r=>availableRun(r))});}

function sourceLabel(r){return r.source==='mine'?t('내가 만든'):r.generated?t('AI 생성'):r.author?.name||'';}
function filteredSearch(){return (state.searchItems||[]).filter(r=>state.resultFilter==='all'||(state.resultFilter==='mine'?r.source==='mine':state.resultFilter==='ai'?r.generated||r.author?.name==='Meta AI':r.source!=='mine'&&!r.generated&&r.author?.name!=='Meta AI'));}
function moveResult(delta){const list=filteredSearch(),next=Math.max(0,Math.min(list.length-1,state.resultIndex+delta));if(next!==state.resultIndex){state.resultIndex=next;render();}}
function wireResults(c){const el=c.querySelector('.recommendation-stack');if(!el)return;el.onkeydown=e=>{if(['ArrowDown','ArrowUp'].includes(e.key)){e.preventDefault();moveResult(e.key==='ArrowDown'?1:-1);}};el.onwheel=e=>{if(e.target.closest('.card-reading')?.scrollHeight>e.target.closest('.card-reading')?.clientHeight)return;e.preventDefault();if(Date.now()-(state.wheelAt||0)<300||Math.abs(e.deltaY)<4)return;state.wheelAt=Date.now();moveResult(e.deltaY>0?1:-1);};let y;el.onpointerdown=e=>{y=e.clientY;};el.onpointerup=e=>{if(y!=null&&Math.abs(e.clientY-y)>35){suppressUntil=Date.now()+350;moveResult(e.clientY<y?1:-1);}y=null;};}
function renderFind(c){
 c.dataset.findMode=state.searchLoading?'loading':state.findMode;
 if(state.searchLoading){c.innerHTML=`<div class="state-copy"><div class="loading-orbit" aria-hidden="true"></div><h1>${t('찾는 중')}</h1><p>${escape(state.searchDraft)}</p></div><div class="actions"><button data-cancel-search>${t('취소')}</button></div>`;return;}
 if(state.findMode==='results'){
 const list=filteredSearch();state.resultIndex=Math.min(state.resultIndex,Math.max(0,list.length-1));const r=list[state.resultIndex];
 c.innerHTML=`<div class="filters">${[['all','전체'],['mine','내가 만든'],['ai','AI 생성'],['other','다른 사용자']].map(([v,l])=>`<button data-result-filter="${v}" aria-pressed="${v===state.resultFilter}">${t(l)}</button>`).join('')}</div><div class="recommendation-stack" tabindex="0" aria-label="${t('추천')}">${r?`${state.resultIndex?`<button class="peek before" data-result-move="-1">${escape(list[state.resultIndex-1].title)}</button>`:''}<button class="recommendation" data-open="${escape(r.id)}" data-kind="search"><div class="card-reading"><h1>${escape(r.title)}</h1><span class="pill">${escape(sourceLabel(r))}</span><p>${escape(r.recommendationReason||r.description)}</p></div><span class="label-small">${t('상세 보기')} ${icon('chev')}</span></button>${list.slice(state.resultIndex+1,state.resultIndex+3).map((x,i)=>`<button class="peek after ${i?'second':''}" data-result-move="${i+1}">${escape(x.title)}</button>`).join('')}`:`<p class="empty">${t('맞는 루틴을 찾지 못했어요.')}</p>`}</div><div class="actions"><button class="text-button" data-search-edit>${t('더 자세하게 설명하기')}</button>${r?`<button class="primary" data-result-start>${t('시작')}</button>`:''}</div>`;return;}
 if(state.findMode==='listening'){c.innerHTML=`<h1>${t('말씀해 주세요')}</h1><div id="voice-panel"></div>`;return;}
 if(state.findMode==='review'){c.innerHTML=`<h1>${t('말한 내용 확인')}</h1><form id="search-form"><label for="search-input">${t('어떤 루틴을 찾고 계신가요?')}</label><textarea id="search-input" maxlength="500" placeholder="${t('막막하다면 지금 상황을 적어도 좋아요.')}">${escape(state.searchDraft)}</textarea>${state.voiceEnabled?'<div id="voice-panel"></div>':''}<div class="actions"><button class="primary wide" type="submit">${t('찾기')}</button></div>${state.metaEnabled?`<small>${t('입력한 내용과 루틴 후보를 Meta AI로 보내 추천합니다.')}</small>`:''}</form>`;return;}
 c.innerHTML=`<h1>${t('지금 필요한 루틴')}</h1><p class="muted">${t('막막하다면 지금 상황을 적어도 좋아요.')}</p><button class="search-entry" data-search-edit>${icon('search')} ${t('어떤 루틴을 찾고 계신가요?')}</button><h2 class="label-small">${t('추천')}</h2><div class="quick-routines">${(state.searchItems||state.items).slice(0,4).map(r=>card(r,state.searchItems?'search':'library')).join('')}</div>${state.voiceEnabled?'<div id="voice-panel"></div>':''}`;
}
function cancelSearch(){state.searchEpoch=(state.searchEpoch||0)+1;state.searchController?.abort();state.searchLoading=false;}
async function searchRoutines(){
 if(state.searchLoading||voiceBusy())return;
 const query=state.searchDraft.trim(),epoch=state.searchEpoch=(state.searchEpoch||0)+1;
 const controller=state.searchController=new AbortController();
 state.searchLoading=true;state.searchItems=null;render();
 const timer=setTimeout(()=>controller.abort(),32000);
 try{
  const result=await api(query&&state.metaEnabled?'/api/recommend':'/api/search',{query,language:locale()},controller.signal);
  if(epoch!==state.searchEpoch||state.view!=='find')return;
  if(query!==state.searchDraft.trim()){message((t("입력이 바뀌었어요. 다시 찾아 주세요.")));return;}
  state.searchItems=result.items;state.searchQuery=query;state.resultIndex=0;state.resultFilter='all';state.searchCount=3;state.findMode=query?'results':'home';message('');
 }catch(e){
  if(epoch===state.searchEpoch){state.findMode='review';error(e.name==='AbortError'?new Error((t("추천 대기가 끝났어요. 입력을 유지했으니 다시 시도해 주세요."))):e);}
 }finally{
  clearTimeout(timer);
  if(epoch===state.searchEpoch){state.searchLoading=false;if(state.view==='find')render();}
 }
}

window.addEventListener('pagehide',()=>{if(voiceBusy())voice.cancel();});
document.addEventListener('visibilitychange',()=>{if(document.hidden&&voiceBusy())voice.cancel();});

var iconPaths={search:'M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14 M15 15l6 6',back:'M15 5l-7 7 7 7',check:'M5 12l4 4L19 6',defer:'M12 3a9 9 0 1 1-8 5 M3 3v6h6 M12 7v5l3 2',skip:'M5 5l10 7-10 7z M19 5v14',book:'M4 4h16v16H4z M8 4v16 M12 9h5 M12 13h5',chev:'M9 5l7 7-7 7'};
function icon(n){return `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${iconPaths[n]||iconPaths.chev}"/></svg>`;}
function renderChrome(){
 document.documentElement.lang=locale();document.title=t('루틴');document.documentElement.dir=languages[locale()].direction;
 const h=document.querySelector('#screen-nav'),isCurrent=state.view==='current';h.innerHTML=isCurrent?`<button data-nav="find">${icon('search')} ${t('찾기')}</button><button data-nav="library">${icon('book')} ${t('보관함')}</button>`:`<button ${state.view==='step-detail'?'data-step-back':state.view==='reservation-detail'?'data-day-back':['add-routine','add-form','add-google'].includes(state.view)?'data-add-back':['detail','preview','conflict-detail','schedule','editor'].includes(state.view)?'data-back':'data-nav="current"'}>${icon('back')} ${t('돌아가기')}</button><button data-nav="current">${t('현재로')}</button>`;
 const settings=document.querySelector('.language');settings.hidden=state.view!=='library';const select=$('#app-language');select.innerHTML=Object.entries(languages).map(([code,l])=>`<option value="${code}">${escape(l.nativeName)}</option>`).join('');select.value=locale();select.disabled=state.busy||voiceBusy()||state.searchLoading;
}
document.querySelector('#app-language').addEventListener('change',e=>{if(voiceBusy()||state.busy||state.searchLoading)return;capture();setLocale(e.target.value);message('');render();});


// A-style relationship geometry. Siblings share their actual parent's center.
// The execution contract has routine-level windows only: never invent step durations.
function stageSize(){const w=Math.min(390,window.innerWidth),h=Math.max(600,window.innerHeight);return {w,h,r:w/2,cy:h/2};}
function orbitMarkup(r,steps,index){const {w,h,r:radius,cy}=stageSize(),point=a=>[radius*Math.cos(a),cy+radius*Math.sin(a)],slots=clockSlots(r.id),current=slots.find(s=>s.role==='current');
 const nodes=slots.length?steps.map((step,i)=>{const s=slots.find(x=>x.id===step.id);if(!s||s.role==='current')return null;return {at:s.atMillis,cls:s.role==='done'?'root-done':'root-pending',done:step.status==='completed',selected:i===index&&state.browseId};}).filter(Boolean):[];
 return `<div class="orbit-scene" tabindex="0" aria-label="${t('궤도 탐색')}"><svg viewBox="0 0 ${w} ${h}" aria-hidden="true"><circle class="parent-core" cx="0" cy="${cy}" r="24"/>${windowOrbit(r.definition.windowStartMillis,r.definition.windowEndMillis,{h,r:radius,cy},false,'routine',{nodes,timer:current?{start:current.startMillis,end:current.endMillis}:null})}<circle cx="${radius}" cy="${cy}" r="18" fill="white"/><circle class="planet" cx="${radius}" cy="${cy}" r="14"/></svg><button class="orbit-parent" data-show-parent>${escape(r.definition.title)}</button>${steps.map((step,i)=>{if(Math.abs(i-index)>1)return '';const [x,y]=point((i-index)*Math.PI/4);return `<button class="orbit-hit orbit-position-${i-index+1}" ${i===index?(state.browseId?'data-return-current':'data-options'):`data-peer="${escape(step.id)}"`} aria-label="${escape(step.title)}"></button>`;}).join('')}</div>`;}
function decorateScreen(){
 const c=$('#content');
 if(['editor','schedule'].includes(state.view))c.querySelector('[data-back]')?.remove();
 wireResults(c);
 if(['detail','preview','conflict-detail'].includes(state.view)){const r=state.view==='preview'?state.draft:state.selected;const ol=c.querySelector('ol');if(ol)ol.outerHTML=stepRows(r.steps);const eyebrow=c.querySelector('.eyebrow');if(eyebrow){eyebrow.className='pill';eyebrow.textContent=state.view==='preview'?t('저장 전 미리보기'):t(r.author.name);const title=c.querySelector('h1');title?.after(eyebrow);}const copy=c.querySelector('.detail');if(copy)copy.insertAdjacentHTML('beforebegin',`<div class="label-small">${t('목적')}</div>`);c.querySelector('[data-back]')?.remove();const existing=state.execution?.workspace.runs.find(x=>availableRun(x)&&x.definition.id===r.id);if(existing&&c.querySelector('[data-start]'))c.querySelector('[data-start]').textContent=t(existing.id===activeRun()?.id?'현재로':'집중하기');}
 if(state.view==='library'){c.insertAdjacentHTML('beforeend',`<button class="store-link" data-nav="catalog">${t('루틴 스토어')} ${icon('chev')}</button>`);}
 if(state.view==='catalog'){const title=c.querySelector('h1');title?.insertAdjacentHTML('afterend',`<input id="catalog-search" aria-label="${t('루틴 검색')}" placeholder="${t('루틴 검색')}">`);c.querySelector('#catalog-search').oninput=e=>{const q=e.target.value.toLocaleLowerCase();c.querySelectorAll('[data-open]').forEach(b=>b.hidden=!b.textContent.toLocaleLowerCase().includes(q));};c.querySelectorAll('[data-open]').forEach(b=>{if(state.items.some(x=>x.origin?.id===b.dataset.open))b.insertAdjacentHTML('beforeend',`<span class="pill">${t('추가됨')}</span>`);});}
 c.querySelector('[data-hold]')?.addEventListener('keydown',e=>{if(e.key==='ContextMenu'||(e.shiftKey&&e.key==='F10')){e.preventDefault();openOptions();}});
 c.querySelectorAll('ol').forEach(el=>el.classList.add('routine-steps'));
 // Browsing peers never changes the engine's current unit or completes a task.
 const orbit=c.querySelector('.orbit-scene');
 const dayLevel=!!c.querySelector('.day-scene');
 const peer=delta=>{if(dayLevel){const items=dayItems(),anchor=dayAnchor(),i=items.findIndex(x=>x.id===(state.dayBrowse||anchor)),next=items[i+delta];if(i>=0&&next){state.turn=delta;state.dayBrowse=next.id===anchor?null:next.id;render();}return;}if(state.showParent)return;const r=activeRun();if(!r)return;const steps=(r.order||r.steps.map(s=>s.id));const i=steps.indexOf(state.browseId||r.currentUnitId);if(steps[i+delta]){state.turn=delta;state.browseId=steps[i+delta];render();}};
 if(orbit&&state.turn){orbit.querySelector('.neighbors')?.animate([{transform:`rotate(${state.turn*45}deg)`},{transform:'rotate(0deg)'}],{duration:240,easing:'ease-out'});state.turn=0;}
 if(orbit){orbit.onwheel=e=>{e.preventDefault();if(Date.now()-(state.wheelAt||0)<300)return;state.wheelAt=Date.now();peer(e.deltaY>0?1:-1);};let start;orbit.onpointerdown=e=>{start={x:e.clientX,y:e.clientY};};orbit.onpointerup=e=>{if(!start)return;const dx=e.clientX-start.x,dy=e.clientY-start.y;start=null;if(Math.max(Math.abs(dx),Math.abs(dy))<40)return;suppressUntil=Date.now()+350;if(Math.abs(dy)>Math.abs(dx)){peer(dy<0?1:-1);}else if(dx>0){if(!dayLevel){state.showParent=true;state.dayBrowse=null;render();}}else if(dayLevel){const key=c.querySelector('.day-scene [data-day-open]')?.dataset.dayOpen;if(key)openDayItem(key);}else{state.showParent=false;state.browseId=null;render();}};orbit.onkeydown=e=>{if(['ArrowUp','ArrowDown','ArrowRight','ArrowLeft'].includes(e.key)){e.preventDefault();if(e.key==='ArrowUp'||e.key==='ArrowDown')peer(e.key==='ArrowDown'?1:-1);else if(e.key==='ArrowRight'){if(!dayLevel){state.showParent=true;state.dayBrowse=null;render();}}else if(dayLevel){const key=c.querySelector('.day-scene [data-day-open]')?.dataset.dayOpen;if(key)openDayItem(key);}else{state.showParent=false;state.browseId=null;render();}}};}
}

function globalIcon(v){return icon(v==='complete'?'check':v);}
function closeOptions(){if(!optionLayer)return;optionLayer.remove();optionLayer=null;document.querySelector('.app').removeAttribute('inert');optionOrigin?.focus({preventScroll:true});}
function openOptions(){
 if(optionLayer||state.busy&&state.executionPending)return;
 optionOrigin=document.activeElement;
 optionLayer=document.createElement('div');optionLayer.className='option-overlay';optionLayer.setAttribute('role','dialog');optionLayer.setAttribute('aria-modal','true');optionLayer.setAttribute('aria-label',t('작업 옵션'));
 optionLayer.innerHTML=`<div class="option-group"><p class="option-label" aria-live="polite"></p><div class="option-buttons">${[['complete','✓','완료'],['defer','↷','미루기'],['skip','⇥','건너뛰기']].map(([v,icon,label])=>`<button data-option="${v}" aria-label="${t(label)}">${globalIcon(v)}</button>`).join('')}</div></div>`;
 document.body.append(optionLayer);document.querySelector('.app').setAttribute('inert','');
 optionLayer.onclick=e=>{if(Date.now()<suppressUntil)return;const action=e.target.closest('[data-option]')?.dataset.option;closeOptions();if(action)run(()=>executeAction(action));};
 optionLayer.onpointermove=e=>highlightOption(e.clientX,e.clientY);
 optionLayer.onfocusin=e=>{const b=e.target.closest('[data-option]');if(b)optionLayer.querySelector('.option-label').textContent=b.getAttribute('aria-label');};
 optionLayer.onkeydown=e=>{if(e.key==='Escape'){e.preventDefault();closeOptions();}if(e.key==='Tab'){const buttons=[...optionLayer.querySelectorAll('button')],i=buttons.indexOf(document.activeElement);e.preventDefault();buttons[i<0?(e.shiftKey?2:0):(i+(e.shiftKey?-1:1)+3)%3].focus();}};
 optionLayer.tabIndex=-1;optionLayer.focus();optionLayer.querySelector('.option-label').textContent='';
}
function highlightOption(x,y){const b=document.elementFromPoint(x,y)?.closest('[data-option]');optionLayer?.querySelectorAll('[data-option]').forEach(el=>el.classList.toggle('selected',el===b));if(optionLayer)optionLayer.querySelector('.option-label').textContent=b?.getAttribute('aria-label')||t('돌아가기');return b?.dataset.option;}
document.addEventListener('click',e=>{if(Date.now()<suppressUntil){e.preventDefault();e.stopImmediatePropagation();}},true);
document.addEventListener('pointerdown',e=>{if(e.button!==0||!e.target.closest('[data-hold]')||state.busy)return;holdPoint={x:e.clientX,y:e.clientY,id:e.pointerId,opened:false};holdTimer=setTimeout(()=>{if(holdPoint){holdPoint.opened=true;openOptions();}},450);});
document.addEventListener('pointermove',e=>{if(!holdPoint)return;if(holdPoint.opened)highlightOption(e.clientX,e.clientY);else if(Math.hypot(e.clientX-holdPoint.x,e.clientY-holdPoint.y)>12){clearTimeout(holdTimer);holdPoint=null;}});
document.addEventListener('pointerup',e=>{clearTimeout(holdTimer);if(!holdPoint)return;const p=holdPoint;holdPoint=null;if(p.opened){const action=highlightOption(e.clientX,e.clientY);suppressUntil=Date.now()+400;closeOptions();if(action&&Math.hypot(e.clientX-p.x,e.clientY-p.y)>8)run(()=>executeAction(action));}});
document.addEventListener('pointercancel',()=>{clearTimeout(holdTimer);holdPoint=null;closeOptions();});

function parentTimeRing(r){const a=r.definition.windowStartMillis,b=r.definition.windowEndMillis;if(!a||!b||b<=a)return '';const f=Math.max(0,Math.min(1,(state.execution.serverNow-a)/(b-a)));return `<circle cx="0" cy="150" r="68" class="parent-time-base"/><circle cx="0" cy="150" r="68" class="parent-time-elapsed" pathLength="1" stroke-dasharray="${f} 1" transform="rotate(-90 0 150)"/>`;}

// Fixed 60-minute time window around "now" (the node): now−30 min at the top end, now+30 min at the bottom end.
// The reservation is drawn at its real length on that scale (elapsed darker), with HH:mm marks to the right of the arc.
// Orbit time scale by depth (shared core OrbitScales, sent by the server as ctx.orbit[depth]): the arc shows
// now ± window/2, the planet is now, and ticks on real clock times slide past it every minute.
// The whole orbit is one clock (user decision 2026-11-04, shared core OrbitClock via ctx.clock): the planet is now,
// every node sits at its time (past up, future down) and everything slides up every minute. The current item is a
// visual timer: thin dark arc from its start to now, thick arc from now to its (expected) end. Ticks are always drawn.
// opts: nodes=[{at,cls,done,selected}], timer={start,end}. The app's time (HH:mm) sits right of the planet.
function windowOrbit(start,end,{h,r,cy},ring=false,depth='day',opts={}){const ctx=state.execution,o=ctx?.orbit?.[depth],hasWindow=start&&end&&end>start;if(!hasWindow&&!o)return '';const now=ctx?.serverNow||Date.now(),span=o?o.scale.windowMinutes*30000:30*60*1000;
 const clip=window.innerHeight>680?190:230,d=Math.max(0,Math.min(cy-(clip+14),h-130-cy)),half=Math.min(50*Math.PI/180,Math.asin(Math.min(1,d/r)));if(half<.05)return '';
 const ang=t=>(t-now)/span*half,pt=(a,rad=r)=>[rad*Math.cos(a),cy+rad*Math.sin(a)],arc=(a,b,cls)=>b>a?`<path class="${cls}" d="M${pt(a)} A${r} ${r} 0 0 1 ${pt(b)}"/>`:'',tick=(a,len,cls)=>`<path class="${cls}" d="M${pt(a,r-len)} L${pt(a,r+len)}"/>`;
 const hm=v=>new Date(v).toLocaleTimeString(locale(),{hour:'2-digit',minute:'2-digit',hour12:false}),clampA=a=>Math.max(-half,Math.min(half,a));
 const nowX=r+(ring?44:24),nowLabel=`<text class="now-time" x="${nowX}" y="${cy}" dominant-baseline="middle">${hm(now)}</text>`;
 let marks=[];
 if(hasWindow){marks=[[start,start<=now],[end,end<now]].filter(([v])=>Math.abs(ang(v))<=half).map(([v,up])=>{let y=pt(ang(v))[1];if(Math.abs(y-cy)<30)y=cy+(up?-30:30);const near=Math.max(0,Math.abs(y-cy)-9);return [v,y,Math.max(Math.sqrt(Math.max(0,r*r-near*near))+12,ring&&Math.abs(y-cy)<43?r+44:0)];});
  if(marks.length===2&&Math.abs(marks[0][1]-marks[1][1])<20)marks.pop();}
 // clock ticks: minor every tickMinutes, a time label on labelEveryMinutes (kept clear of the planet and the window labels)
 const scaleTicks=o?o.ticks.map(k=>{const a=k.offset*half,[x,y]=pt(a);const free=Math.abs(y-cy)>(ring?46:26)&&marks.every(([,my])=>Math.abs(my-y)>20);
   return tick(a,k.label?6:3,k.label?'clock-tick major':'clock-tick')+(k.label&&free?`<text class="clock-label" x="${x-12}" y="${y}" text-anchor="end" dominant-baseline="middle">${hm(k.atMillis)}</text>`:'');}).join('')
  :[-half,half].map(a=>{const [x,y]=pt(a);return tick(a,5,'window-tick')+`<text class="window-end" x="${x-10}" y="${y}" text-anchor="end" dominant-baseline="middle">${hm(now+a/half*span)}</text>`;}).join('');
 const nodes=(opts.nodes||[]).filter(n=>Math.abs(ang(n.at))<=half).map(n=>{const [x,y]=pt(ang(n.at));return `<g class="clock-node ${n.cls}${n.selected?' selected':''}"><circle cx="${x}" cy="${y}" r="${n.size||9}"/>${n.done?`<path d="M${x-4.5} ${y}l3 3 6-7"/>`:''}</g>`;}).join('');
 const tm=opts.timer;
 const timer=tm&&tm.end>now?arc(clampA(ang(tm.start)),0,'timer-elapsed')+arc(0,clampA(ang(tm.end)),'timer-remaining')+(Math.abs(ang(tm.end))<=half?tick(ang(tm.end),7,'window-mark-tick'):'')
  :hasWindow?(()=>{const sa=Math.max(-half,ang(start)),ea=Math.min(half,ang(end));return arc(sa,Math.min(0,ea),'timer-elapsed')+arc(Math.max(0,sa),ea,'timer-remaining');})():'';
 return arc(-half,half,'window-base')+timer+scaleTicks
  +(hasWindow?[start,end].filter(v=>Math.abs(ang(v))<=half).map(v=>tick(ang(v),7,'window-mark-tick')).join(''):'')
  +marks.map(([v,y,x])=>`<text class="window-mark" x="${x}" y="${y}" dominant-baseline="middle">${hm(v)}</text>`).join('')
  +`<g class="clock-nodes">${nodes}</g>`+nowLabel;}
// Clock slots from the server (shared core OrbitClock). Older servers: none (nodes fall back to their atMillis).
function clockSlots(runId){const c=state.execution?.clock;return runId?c?.runs?.[runId]||[]:c?.day||[];}
function rootOrbit(title,steps=[],start=null,end=null){const {w,h,r,cy}=stageSize();const nodes=steps.slice(0,3).map((step,i)=>{const a=(-100+i*100)*Math.PI/180;return `<circle cx="${r+34*Math.cos(a)}" cy="${cy+34*Math.sin(a)}" r="4" class="${step.status==='completed'?'root-done':'root-pending'}"/>`;}).join('');return `<div class="orbit-scene root-scene" tabindex="0" aria-label="${t('궤도 탐색')}"><svg viewBox="0 0 ${w} ${h}" aria-hidden="true">${windowOrbit(start,end,{h,r,cy},steps.length>0)}${steps.length?`<circle cx="${r}" cy="${cy}" r="34" class="satellite-orbit"/>`:''}${nodes}<circle cx="${r}" cy="${cy}" r="18" fill="white"/><circle cx="${r}" cy="${cy}" r="14" class="planet"/></svg>${steps.length?`<button class="orbit-hit child-hit" data-child aria-label="${t('하위 작업')}"></button>`:''}</div>`;}

await run(async()=>{await load();await refreshExecution();render();if(state.executionPending)executionMessage((t("실행 결과 확인이 필요합니다.")));});

let resizeTimer;
window.addEventListener('resize',()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(()=>{if(state.view==='current'&&!optionLayer)render();},100);});
