import {t, locale} from '/i18n.js';
export class VoiceCapture {
 constructor({onState,onDraft}){this.onState=onState;this.onDraft=onDraft;this.epoch=0;this.state='idle';this.text='';}
 emit(state,text=this.text,note=''){this.state=state;this.text=text;this.onState({state,text,note});}
 async request(action,body={}){
  const control=new AbortController(),timer=setTimeout(()=>control.abort(),10000);
  try{const r=await fetch('/api/voice/'+action,{method:'POST',headers:{'Content-Type':'application/json','X-Routine-App':'local','X-Routine-Language':locale()},body:JSON.stringify(body),signal:control.signal});const data=await r.json();if(!r.ok)throw new Error(data.error?.message||(t("음성 연결을 확인해 주세요.")));return data;}
  finally{clearTimeout(timer);}
 }
 cleanup(){clearTimeout(this.limit);this.stream?.getTracks().forEach(t=>t.stop());this.stream=null;this.node?.disconnect();this.node=null;this.source?.disconnect();this.source=null;this.context?.close().catch(()=>{});this.context=null;}
 cancel(){this.epoch++;const token=this.token;this.token=null;this.cleanup();if(token)this.request('cancel',{session:token}).catch(()=>{});this.emit('idle','',(t("입력을 유지했습니다.")));}
 async start(base){
  if(['permission','listening','finishing'].includes(this.state))return;
  const epoch=++this.epoch;this.base=base;this.text='';this.token=null;this.seq=0;this.queued=0;this.chain=Promise.resolve();this.emit('permission','',(t("마이크 연결 중")));
  try{
   if(!navigator.mediaDevices?.getUserMedia||!window.AudioWorkletNode)throw new Error((t("이 브라우저에서는 글로 입력해 주세요.")));
   const stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true},video:false});
   if(epoch!==this.epoch){stream.getTracks().forEach(t=>t.stop());return;}this.stream=stream;
   this.context=new AudioContext({sampleRate:24000});await this.context.resume();
   if(epoch!==this.epoch)return;
   await this.context.audioWorklet.addModule('/voice-worklet.js');
   if(epoch!==this.epoch)return;
   const session=await this.request('start',{language:locale()});
   if(epoch!==this.epoch){this.request('cancel',{session:session.session}).catch(()=>{});return;}
   this.token=session.session;this.node=new AudioWorkletNode(this.context,'routine-pcm');
   this.node.port.onmessage=e=>{
    if(epoch!==this.epoch)return;
    if(e.data.flushed){this.resolveFlush?.();return;}
    if(!e.data.pcm)return;
    if(++this.queued>10){this.fail(epoch,(t("음성 연결이 느려졌어요. 인식한 내용을 확인해 주세요.")));return;}
    const bytes=new Uint8Array(e.data.pcm);let binary='';for(const b of bytes)binary+=String.fromCharCode(b);
    const seq=this.seq++,audio=btoa(binary),token=this.token;
    this.chain=this.chain.then(async()=>{if(epoch!==this.epoch)return;const result=await this.request('chunk',{session:token,seq,audio});this.apply(result,epoch);}).catch(e=>this.fail(epoch,e.message)).finally(()=>{if(epoch===this.epoch)this.queued--;});
   };
   this.source=this.context.createMediaStreamSource(stream);this.source.connect(this.node);
   const silent=this.context.createGain();silent.gain.value=0;this.node.connect(silent);silent.connect(this.context.destination);
   this.emit('listening','',(t("말씀해 주세요")));this.limit=setTimeout(()=>this.stop(),58000);
  }catch(e){if(epoch===this.epoch)this.fail(epoch,e.name==='NotAllowedError'?(t("마이크 권한을 허용하거나 글로 입력해 주세요.")):e.message);}
 }
 apply(result,epoch){
  if(epoch!==this.epoch)return;
  if(result.state==='error'){
   if(typeof result.text==='string')this.text=result.text;
   throw new Error((t("음성 연결이 끊겼어요. 인식한 내용을 확인해 주세요.")));
  }
  if(result.state==='cancelled')return;
  if(result.state==='done'){
   this.epoch++;this.cleanup();this.token=null;
   if(result.text?.trim()){this.onDraft([this.base,result.text.trim()].filter(Boolean).join(' '));this.emit('review',result.text,(t("인식 내용을 확인·수정한 뒤 찾아 주세요.")));}
   else this.emit('review','',(t("말소리가 인식되지 않았어요. 다시 말하거나 글로 입력해 주세요.")));
  }else this.emit(this.state,result.text||'',this.state==='finishing'?(t("인식 마무리 중")):(t("듣고 있어요")));
 }
 fail(epoch,note){
  if(epoch!==this.epoch)return;const partial=this.text,base=this.base;
  this.cancel();if(partial.trim())this.onDraft([base,partial.trim()].filter(Boolean).join(' '));
  this.emit('error',partial,note||(t("음성 입력을 마치지 못했어요. 글로 계속할 수 있어요.")));
 }
 async stop(){
  if(this.state!=='listening')return;
  const epoch=this.epoch,token=this.token;this.emit('finishing',this.text,(t("인식 마무리 중")));clearTimeout(this.limit);
  try{
   await Promise.race([new Promise(resolve=>{this.resolveFlush=resolve;this.node.port.postMessage('flush');}),new Promise((_,reject)=>setTimeout(()=>reject(new Error((t("음성 마무리를 확인해 주세요.")))),2000))]);
   if(epoch!==this.epoch)return;this.cleanup();await this.chain;if(epoch!==this.epoch)return;
   let result=await this.request('stop',{session:token});const end=Date.now()+13000;
   while(epoch===this.epoch&&result.state==='finishing'&&Date.now()<end){this.apply(result,epoch);await new Promise(r=>setTimeout(r,250));result=await this.request('poll',{session:token});}
   if(epoch!==this.epoch)return;
   if(result.state==='finishing')throw new Error((t("인식이 늦어지고 있어요. 표시된 내용을 확인해 주세요.")));
   this.apply(result,epoch);
  }catch(e){this.fail(epoch,e.message);}
 }
}
