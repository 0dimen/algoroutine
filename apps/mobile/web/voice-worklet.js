// Stream mono signed PCM at 24 kHz, 200 ms per message. No audio recording file.
class RoutinePCM extends AudioWorkletProcessor {
 constructor(){super();this.buffer=[];this.phase=0;this.sum=0;this.count=0;this.active=true;this.port.onmessage=e=>{if(e.data==='flush'){this.active=false;this.flush();this.port.postMessage({flushed:true});}};}
 flush(){if(!this.buffer.length)return;const pcm=new Int16Array(this.buffer);this.port.postMessage({pcm:pcm.buffer},[pcm.buffer]);this.buffer=[];}
 process(inputs){
  if(!this.active)return true;
  const input=inputs[0]?.[0];if(!input)return true;
  for(const value of input){
   this.sum+=value;this.count++;this.phase+=24000;
   while(this.phase>=sampleRate){
    const v=Math.max(-1,Math.min(1,this.sum/this.count));this.buffer.push(Math.round(v*(v<0?32768:32767)));
    this.phase-=sampleRate;if(this.buffer.length>=4800)this.flush();
   }
   if(this.phase<24000){this.sum=0;this.count=0;}
  }
  return true;
 }
}
registerProcessor('routine-pcm',RoutinePCM);
