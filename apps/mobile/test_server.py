import json,tempfile,threading,unittest
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from pathlib import Path
from server import make_server

class ApiTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.server=make_server(Path(self.tmp.name)/'db',0);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.url='http://127.0.0.1:'+str(self.server.server_port)
 def tearDown(self):self.server.shutdown();self.server.server_close();self.tmp.cleanup()
 def call(self,path,body=None,headers=None):
  h={'Content-Type':'application/json','X-Routine-App':'local'};h.update(headers or {});req=Request(self.url+path,data=json.dumps(body).encode() if body is not None else None,headers=h)
  try:
   with urlopen(req) as r:return r.status,json.load(r)
  except HTTPError as r:return r.code,json.load(r)
 def test_api_roundtrip(self):
  status,r=self.call('/api/commands',{'commandId':'one','kind':'saveDefinition','content':{'title':'API 루틴','steps':[{'id':'1','title':'시작'}]}});self.assertEqual(status,200);self.assertEqual(self.call('/api/library')[1]['items'][0],r['routine'])
 def test_search_read_only_and_validation(self):
  before=self.call('/api/library')[1]
  code,result=self.call('/api/search',{'query':'문서'})
  self.assertEqual(code,200);self.assertEqual(result['items'][0]['id'],'report-start')
  self.assertEqual(self.call('/api/library')[1],before)
  self.assertEqual(self.call('/api/search',{'query':None})[0],400)
  self.assertEqual(self.call('/api/search',{'query':'문서'}, {'Origin':'https://example.com'})[0],403)
 def test_cross_origin_mutation_denied(self):
  self.assertEqual(self.call('/api/commands',{}, {'Origin':'https://example.com'})[0],403)
 def test_untrusted_host_denied(self):
  self.assertEqual(self.call('/api/library',headers={'Host':'example.com'})[0],403)
 def test_unknown_and_malformed_are_not_empty_library(self):
  self.assertEqual(self.call('/api/routine?id=unknown')[0],404);self.assertEqual(self.call('/api/commands',[])[0],400)
 def test_path_traversal_not_served(self):
  self.assertEqual(self.call('/../store.py')[0],404)

if __name__=='__main__':unittest.main()
