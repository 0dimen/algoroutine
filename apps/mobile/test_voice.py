import base64,json,queue,time,unittest
from voice import VoiceSession,VoiceManager
from store import DomainError

class Socket:
 def __init__(self):self.events=queue.Queue();self.sent=[];self.closed=False
 def recv(self):return self.events.get(timeout=2)
 def send(self,value):self.sent.append(value)
 def send_binary(self,value):self.sent.append(value)
 def close(self,timeout=0):self.closed=True;self.events.put('')
 def emit(self,**value):self.events.put(json.dumps(value));time.sleep(.02)

class VoiceTests(unittest.TestCase):
 def setUp(self):self.ws=Socket();self.s=VoiceSession(self.ws)
 def tearDown(self):self.s.cancel()
 def test_partial_replaced_and_final_accepted(self):
  self.ws.emit(type='transcript',transcript='보고',final=False)
  self.ws.emit(type='transcript',transcript='보고서',final=False)
  self.assertEqual(self.s.snapshot()['text'],'보고서')
  self.s.stop();self.ws.emit(type='transcript',transcript='보고서 작성',final=True)
  self.assertEqual(self.s.snapshot()['state'],'done');self.assertTrue(self.ws.closed)
 def test_chunk_duplicate_and_out_of_order(self):
  data=base64.b64encode(b'\0'*9600).decode()
  self.s.chunk(data,0);self.s.chunk(data,0)
  self.assertEqual(len(self.ws.sent),1)
  with self.assertRaises(DomainError):self.s.chunk(data,2)
  for raw,seq in [('?',1),(data,-1),(data,True),(base64.b64encode(b'a').decode(),1)]:
   with self.assertRaises(DomainError):self.s.chunk(raw,seq)
 def test_cancel_discards_late_text(self):
  self.ws.emit(type='transcript',transcript='임시',final=False);self.s.cancel()
  self.ws.emit(type='transcript',transcript='늦은 결과',final=True)
  self.assertEqual(self.s.snapshot()['state'],'cancelled');self.assertEqual(self.s.snapshot()['text'],'')
 def test_stop_is_idempotent(self):
  self.s.stop();self.s.stop();self.assertEqual(len(self.ws.sent),1)
 def test_provider_error_never_exposes_message(self):
  self.ws.emit(type='error',message='private bearer key')
  self.assertEqual(self.s.snapshot()['error'],'VOICE_PROVIDER_ERROR')
  self.assertNotIn('private',json.dumps(self.s.snapshot()))
 def test_silent_final_and_disconnect_differ(self):
  self.s.stop();self.ws.emit(type='transcript',transcript='',final=True)
  self.assertEqual(self.s.snapshot()['state'],'done');self.assertEqual(self.s.snapshot()['text'],'')
  other=VoiceSession(Socket());other.ws.close();time.sleep(.02)
  self.assertEqual(other.snapshot()['state'],'error');other.cancel()
 def test_manager_single_session_and_token(self):
  m=VoiceManager(lambda:self.s);result=m.start()
  with self.assertRaises(DomainError):m.start()
  with self.assertRaises(DomainError):m.action('poll',{'session':'other'})
  self.assertEqual(m.action('poll',{'session':result['session']})['state'],'listening')
  m.close()
 def test_excess_audio_stops_stream(self):
  self.s.sent=48000*60
  out=self.s.chunk(base64.b64encode(b'\0'*9600).decode(),0)
  self.assertEqual(out['error'],'VOICE_LIMIT')
 def test_finishing_gets_full_twelve_second_deadline(self):
  from unittest.mock import patch
  self.s.stop();stopped=self.s.stopped
  self.s.clock=lambda:stopped+9
  # Run the watchdog synchronously with a deterministic clock, no real wait.
  checks=[]
  def advance(_):
   checks.append(self.s.snapshot()['state'])
   if len(checks)==2:
    self.assertEqual(self.s.snapshot()['state'],'finishing')
    self.s.clock=lambda:stopped+12.1
  with patch('voice.time.sleep',advance):self.s.watchdog()
  self.assertEqual(len(checks),2)
  self.assertEqual(self.s.snapshot()['error'],'VOICE_TIMEOUT')

 def test_stalled_session_expires(self):
  self.s.touched-=9;time.sleep(.6)
  self.assertEqual(self.s.snapshot()['error'],'VOICE_TIMEOUT');self.assertTrue(self.ws.closed)


class VoiceHttpTests(unittest.TestCase):
 def test_local_origin_and_capability(self):
  import tempfile,threading
  from pathlib import Path
  from urllib.request import Request,urlopen
  from urllib.error import HTTPError
  from server import make_server
  with tempfile.TemporaryDirectory() as tmp:
   server=make_server(Path(tmp)/'db',0,voice_factory=lambda:VoiceSession(Socket()))
   threading.Thread(target=server.serve_forever,daemon=True).start()
   base='http://127.0.0.1:'+str(server.server_port)
   def call(action,body,origin=None):
    headers={'Content-Type':'application/json','X-Routine-App':'local'}
    if origin:headers['Origin']=origin
    with urlopen(Request(base+'/api/voice/'+action,data=json.dumps(body).encode(),headers=headers),timeout=3) as r:return json.load(r)
   try:
    with self.assertRaises(HTTPError) as e:call('start',{},'https://other.example')
    self.assertEqual(e.exception.code,403);self.assertIsNone(server.voice.current)
    result=call('start',{});self.assertEqual(result['state'],'listening')
    with self.assertRaises(HTTPError) as e:call('poll',{'session':'wrong'})
    self.assertEqual(e.exception.code,404)
    self.assertEqual(call('cancel',{'session':result['session']})['state'],'cancelled')
    self.assertEqual(server.store.library()['items'],[])
   finally:server.voice.close();server.shutdown();server.server_close()

if __name__=='__main__':unittest.main()
