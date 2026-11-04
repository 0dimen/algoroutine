"""Real KMP transport test; separate from fast gateway unit tests."""
import json,pathlib,ssl,sys,threading,unittest,urllib.request
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]/'mobile'))
from test_execution_integration import IntegrationFixture
from prepare import prepare
from gateway import make_server
class DeviceExecution(IntegrationFixture):
 @classmethod
 def setUpClass(cls):
  super().setUpClass();cls.profile=cls.base/'profile';prepare('127.0.0.1',cls.profile)
  cls.settings=json.loads((cls.profile/'client.json').read_text());cls.ssl=ssl.create_default_context(cafile=str(cls.profile/'cert.pem'))
  cls.gateway=make_server(cls.profile,port=0,backend_port=cls.port);threading.Thread(target=cls.gateway.serve_forever,daemon=True).start()
 @classmethod
 def tearDownClass(cls):
  cls.gateway.shutdown();cls.gateway.server_close();super().tearDownClass()
 def device(self,path,body=None):
  req=urllib.request.Request(f'https://127.0.0.1:{self.gateway.server_port}'+path,data=None if body is None else json.dumps(body).encode(),headers={'Authorization':'Bearer '+self.settings['token'],'Content-Type':'application/json'})
  with urllib.request.urlopen(req,context=self.ssl,timeout=8) as res:return json.load(res)
 def test_find_start_complete_and_replay(self):
  routine=self.call('/api/commands',{'commandId':'create-device','kind':'saveDefinition','content':{'title':'Device test','steps':[{'id':'one','title':'Open document'},{'id':'two','title':'Write heading'}]}})['routine']
  self.assertIn(routine['id'],[r['id'] for r in self.device('/search',{'query':'Device test'})['items']])
  w=self.device('/context')['workspace']
  start={'id':'start-device','kind':'start','occurrenceId':'device-run','expectedRevision':w['revision'],'definition':{'id':routine['id'],'version':routine['version'],'title':'ignored','author':'','steps':[]}}
  first=self.device('/command',start);self.assertTrue(first['result']['accepted'])
  w=first['context']['workspace'];r=next(r for r in w['runs'] if r['id']=='device-run')
  command={'id':'complete-device','kind':'complete','occurrenceId':r['id'],'expectedRevision':r['revision'],'unitId':r['currentUnitId'],'expectedFocusRevision':w['focusRevision']}
  out=self.device('/command',command);self.assertTrue(out['result']['accepted']);self.assertEqual(out['context']['workspace']['runs'][0]['currentUnitId'],'two')
  again=self.device('/command',command)
  self.assertEqual(again['result'],out['result']);self.assertEqual(again['context']['workspace'],out['context']['workspace'])
if __name__=='__main__':unittest.main()
