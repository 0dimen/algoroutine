// Synthetic transport only: no browser microphone or external ASR.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const data=s=>'data:text/javascript;base64,'+Buffer.from(s).toString('base64');
const i18n=data(fs.readFileSync(__dirname+'/web/i18n.js','utf8').replace("'/messages.js'",JSON.stringify(data(fs.readFileSync(__dirname+'/web/messages.js','utf8')))));
const capture=()=>import(data(fs.readFileSync(__dirname+'/web/voice.js','utf8').replace("'/i18n.js'",JSON.stringify(i18n))));
test('disconnect preserves latest server partial in editable draft',async()=>{
 const {VoiceCapture}=await capture();let draft;
 const v=new VoiceCapture({onState:()=>{},onDraft:t=>draft=t});
 v.base='기존 입력';v.state='listening';v.text='이전 부분';v.token='old';v.request=async()=>({});
 try{v.apply({state:'error',text:'마지막 부분',error:'VOICE_DISCONNECTED'},v.epoch)}catch(e){v.fail(v.epoch,e.message)}
 assert.equal(draft,'기존 입력 마지막 부분');assert.equal(v.state,'error');
});
test('cancel and restart ignores old final and cleanup',async()=>{
 const {VoiceCapture}=await capture();let draft;const states=[];
 const v=new VoiceCapture({onState:s=>states.push(s.state),onDraft:t=>draft=t});
 v.state='listening';v.token='old';v.request=async()=>({});const old=v.epoch;
 v.cancel();v.state='listening';v.token='new';v.text='새 부분';const current=v.epoch;
 v.apply({state:'done',text:'늦은 문장'},old);
 assert.equal(v.token,'new');assert.equal(v.epoch,current);assert.equal(v.text,'새 부분');assert.equal(draft,undefined);
});
