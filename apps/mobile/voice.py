"""Bounded realtime ASR bridge. PCM and transcripts stay in memory only."""
import base64
import json
import secrets
import threading
import time
from store import DomainError
from localization import normalize,LANGUAGES

MODEL='muse-voice-transcribe-1.0'
RATE_BYTES=48000

class VoiceSession:
    def __init__(self, ws, clock=time.monotonic):
        self.ws=ws;self.clock=clock;self.started=clock();self.touched=self.started
        self.token=secrets.token_urlsafe(24);self.lock=threading.RLock()
        self.state='listening';self.text='';self.error=None;self.seq=0;self.sent=0;self.stopped=None
        self.closed=False
        threading.Thread(target=self.receive,daemon=True).start()
        threading.Thread(target=self.watchdog,daemon=True).start()

    def snapshot(self):
        with self.lock:return {'session':self.token,'state':self.state,'text':self.text,'error':self.error,'audioMs':self.sent*1000//RATE_BYTES}

    def close_socket(self):
        if not self.closed:
            self.closed=True
            try:self.ws.close(timeout=0)
            except Exception:pass

    def fail(self, code):
        with self.lock:
            if self.state in ('done','cancelled','error'):return
            self.error=code;self.state='error'
        self.close_socket()

    def receive(self):
        try:
            while True:
                message=self.ws.recv()
                if not message:
                    with self.lock:finished=self.state in ('done','cancelled','error')
                    if not finished:self.fail('VOICE_DISCONNECTED')
                    return
                event=json.loads(message)
                if event.get('type')=='error':self.fail('VOICE_PROVIDER_ERROR');return
                if event.get('type')=='transcript':
                    text=event.get('transcript')
                    if not isinstance(text,str) or len(text)>10000:self.fail('VOICE_INVALID');return
                    with self.lock:
                        if self.state in ('cancelled','error','done'):return
                        self.text=text
                        if event.get('final') is True:self.state='done'
                    if event.get('final') is True:self.close_socket();return
        except Exception:
            self.fail('VOICE_DISCONNECTED')  # Never expose upstream error/handshake text.

    def watchdog(self):
        while True:
            time.sleep(.5)
            with self.lock:
                if self.state in ('done','cancelled','error'):return
                now=self.clock()
                expired=((self.state=='listening' and now-self.touched>8) or now-self.started>75 or
                         (self.stopped is not None and now-self.stopped>12))
            if expired:self.fail('VOICE_TIMEOUT');return

    def chunk(self, encoded, seq):
        if not isinstance(encoded,str) or len(encoded)>32000 or type(seq) is not int or seq<0:
            raise DomainError('VOICE_INVALID','음성 조각을 확인할 수 없어요.')
        try:raw=base64.b64decode(encoded,validate=True)
        except ValueError:raise DomainError('VOICE_INVALID','음성 조각을 확인할 수 없어요.')
        if not raw or len(raw)>24000 or len(raw)%2:
            raise DomainError('VOICE_INVALID','음성 조각을 확인할 수 없어요.')
        with self.lock:
            if self.state!='listening':return self.snapshot()
            if seq==self.seq-1:return self.snapshot()  # Lost response: no duplicate audio.
            if seq!=self.seq:raise DomainError('VOICE_SEQUENCE','음성 연결 순서가 달라졌어요.',409)
            if self.sent+len(raw)>RATE_BYTES*60 or self.sent+len(raw)>RATE_BYTES*(self.clock()-self.started+2):
                self.fail('VOICE_LIMIT');return self.snapshot()
            try:self.ws.send_binary(raw)
            except Exception:self.fail('VOICE_DISCONNECTED');return self.snapshot()
            self.sent+=len(raw);self.seq+=1;self.touched=self.clock()
            return self.snapshot()

    def stop(self):
        with self.lock:
            if self.state=='listening':
                self.state='finishing';self.stopped=self.clock();self.touched=self.stopped
                try:self.ws.send(json.dumps({'type':'endStream'}))
                except Exception:self.fail('VOICE_DISCONNECTED')
            return self.snapshot()

    def cancel(self):
        with self.lock:self.state='cancelled';self.text=''
        self.close_socket();return self.snapshot()

class VoiceManager:
    def __init__(self, factory):self.factory=factory;self.lock=threading.Lock();self.current=None
    def start(self, language="en"):
        with self.lock:
            if self.current and self.current.snapshot()['state'] in ('listening','finishing'):
                raise DomainError('VOICE_BUSY','이미 음성을 듣고 있어요.',409)
            self.current=self.factory(language=language) if self.factory is meta_voice_session else self.factory()
            return self.current.snapshot()
    def action(self, action, body):
        if action=='start':return self.start(body.get('language','en'))
        with self.lock:session=self.current
        if not session or not isinstance(body.get('session'),str) or not secrets.compare_digest(body['session'],session.token):
            raise DomainError('VOICE_NOT_FOUND','음성 입력을 다시 시작해 주세요.',404)
        if action=='chunk':return session.chunk(body.get('audio'),body.get('seq'))
        if action=='stop':return session.stop()
        if action=='cancel':return session.cancel()
        if action=='poll':return session.snapshot()
        raise DomainError('NOT_FOUND','음성 동작을 확인해 주세요.',404)
    def close(self):
        if self.current:self.current.cancel()

def meta_voice_session(language="en"):
    try:import websocket
    except ImportError:raise DomainError('VOICE_UNAVAILABLE','음성 연결 준비가 필요해요. 글로 입력해 주세요.',503)
    from meta_provider import MetaProvider
    key=MetaProvider.local()._key
    ws=None
    try:
        ws=websocket.create_connection('wss://api.meta.ai/v1/asr/realtime',timeout=8,
                                       enable_multithread=True,redirect_limit=0)
        ws.send(json.dumps({'authorization':{'accessToken':'Bearer '+key},'model':MODEL,
                            'audioEncoding':'PCM_24KHZ','mode':'PUSH_TO_TALK',
                            'partialMode':'CUMULATIVE','languageBias':[LANGUAGES[normalize(language)]['speechBias']],'emitAudioProgress':False}))
        reply=json.loads(ws.recv())
        if not reply.get('sessionId'):raise ValueError('handshake')
        ws.settimeout(15)
        return VoiceSession(ws)
    except Exception:
        if ws:
            try:ws.close(timeout=0)
            except Exception:pass
        raise DomainError('VOICE_UNAVAILABLE','음성 연결을 확인해 주세요. 글로도 입력할 수 있어요.',503) from None
