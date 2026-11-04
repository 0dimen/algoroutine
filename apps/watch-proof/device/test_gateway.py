import http.client,http.server,json,pathlib,ssl,tempfile,threading,unittest
from gateway import make_server
from prepare import prepare

class Backend(http.server.BaseHTTPRequestHandler):
    calls=[]
    def log_message(self,*args):pass
    def do_GET(self):
        self.calls.append((self.command,self.path))
        self.send_response(200);self.end_headers();self.wfile.write(b'{"revision":1}')
    def do_POST(self):
        self.calls.append((self.command,self.path,self.rfile.read(int(self.headers.get('Content-Length',0))),self.headers.get('X-Routine-App'),self.headers.get('Authorization')))
        self.send_response(200);self.end_headers();self.wfile.write(b'{"accepted":true}')

class GatewayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.profile=pathlib.Path(cls.temp.name)/'profile'
        prepare('127.0.0.1',cls.profile)
        cls.client=json.loads((cls.profile/'client.json').read_text())
        cls.backend=http.server.ThreadingHTTPServer(('127.0.0.1',0),Backend)
        cls.gateway=make_server(cls.profile,port=0,backend_port=cls.backend.server_port)
        cls.context=ssl.create_default_context(cafile=str(cls.profile/'cert.pem'))
        for server in (cls.backend,cls.gateway):threading.Thread(target=server.serve_forever,daemon=True).start()
    @classmethod
    def tearDownClass(cls):
        for s in (cls.gateway,cls.backend):s.shutdown();s.server_close()
        cls.temp.cleanup()
    def request(self,path='/context',method='GET',headers=None,body=None,context=None,host='127.0.0.1'):
        c=http.client.HTTPSConnection(host,self.gateway.server_port,context=context or self.context,timeout=3)
        h={'Authorization':'Bearer '+self.client['token']};h.update(headers or {})
        try:c.request(method,path,body=body,headers=h);r=c.getresponse();return r.status,r.read()
        finally:c.close()
    def test_tls_authenticated_context(self):self.assertEqual(self.request(),(200,b'{"revision":1}'))
    def test_token_required(self):self.assertEqual(self.request(headers={'Authorization':''})[0],401)
    def test_wrong_token(self):self.assertEqual(self.request(headers={'Authorization':'Bearer wrong'})[0],401)
    def test_origin_rejected(self):self.assertEqual(self.request(headers={'Origin':'https://example.com'})[0],403)
    def test_host_rejected(self):self.assertEqual(self.request(headers={'Host':'example.com'})[0],403)
    def test_path_query_rejected(self):
        for path in ('/events','/context?token=x','/../context','/recommend'):
            with self.subTest(path=path):self.assertEqual(self.request(path)[0],404)
    def test_wrong_method(self):self.assertEqual(self.request('/command')[0],404)
    def test_transfer_encoding_rejected(self):self.assertEqual(self.request('/command','POST',{'Transfer-Encoding':'chunked'})[0],400)
    def test_oversize(self):self.assertEqual(self.request('/command','POST',body=b'a'*65537)[0],413)
    def test_forward_once_and_strip_credential(self):
        before=len(Backend.calls);body=b'{"commandId":"idempotent-1"}'
        self.assertEqual(self.request('/command','POST',body=body)[0],200)
        self.assertEqual(Backend.calls[before:],[('POST','/command',body,'local',None)])
    def test_untrusted_certificate_rejected(self):
        with self.assertRaises(ssl.SSLCertVerificationError):self.request(context=ssl.create_default_context())
    def test_wrong_hostname_rejected(self):
        with self.assertRaises(ssl.SSLCertVerificationError):self.request(host='localhost')
    def test_no_public_bind(self):
        with self.assertRaises(ValueError):make_server(self.profile,bind='0.0.0.0',port=0)
    def test_refuse_profile_inside_repo(self):
        with self.assertRaises(ValueError):prepare('127.0.0.1',pathlib.Path(__file__).parent/'must-not-exist')
if __name__=='__main__':unittest.main()
