"""Authenticated development-only TLS bridge to the loopback execution server.
No public listener, query logging, model keys, redirects, or automatic mutation retries.
"""
import argparse,hmac,http.client,http.server,ipaddress,json,pathlib,ssl

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def reply(self,status,body=b'{}'):
        self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def handle_request(self):
        self.connection.settimeout(8)
        if len(self.headers.get_all('Host',[]))!=1 or self.headers.get('Origin') or self.headers.get('Host') not in self.server.allowed_hosts:return self.reply(403)
        if len(self.headers.get_all('Authorization',[]))!=1 or not hmac.compare_digest(self.headers.get('Authorization','').encode(), ('Bearer '+self.server.token).encode()):return self.reply(401)
        allowed={'GET':{'/context','/library','/reservations'},'POST':{'/command','/search'}}
        if self.path not in allowed.get(self.command,set()):return self.reply(404)
        if self.headers.get('Transfer-Encoding'):return self.reply(400)
        lengths=self.headers.get_all('Content-Length',[])
        if len(lengths)>1:return self.reply(400)
        try:size=int(lengths[0]) if lengths else 0
        except ValueError:return self.reply(400)
        if size<0 or size>65536:return self.reply(413)
        if self.command=='GET' and size:return self.reply(400)
        backend=http.client.HTTPConnection('127.0.0.1',self.server.backend_port,timeout=6)
        try:
            body=self.rfile.read(size)
            if len(body)!=size:return self.reply(400)
            backend.request(self.command,self.path,body=body,headers={'Content-Type':'application/json','X-Routine-App':'local'})
            result=backend.getresponse();payload=result.read(1048577)
            if len(payload)>1048576 or 300<=result.status<400:return self.reply(502)
            self.reply(result.status,payload)
        except (OSError,http.client.HTTPException):self.reply(502)
        finally:backend.close()
    do_GET=handle_request
    do_POST=handle_request

class Server(http.server.ThreadingHTTPServer):
    daemon_threads=True
    def get_request(self):
        sock,addr=super().get_request();sock.settimeout(3)
        try:return self.context.wrap_socket(sock,server_side=True),addr
        except OSError:sock.close();raise

def make_server(profile,bind='127.0.0.1',port=8792,backend_port=8791):
    root=pathlib.Path(profile);client=json.loads((root/'client.json').read_text())
    if bind not in ('127.0.0.1',client['host']):raise ValueError('Bind must match private profile host or loopback')
    address=ipaddress.ip_address(bind)
    if not address.is_private or address.is_unspecified:raise ValueError('Private address required')
    server=Server((bind,port),Handler);server.backend_port=backend_port;server.token=client['token']
    server.allowed_hosts={h+':'+str(server.server_port) for h in (bind,client['host'],'127.0.0.1')}
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.minimum_version=ssl.TLSVersion.TLSv1_2;context.load_cert_chain(root/'cert.pem',root/'key.pem')
    server.context=context;return server
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--profile',required=True);p.add_argument('--bind',default='127.0.0.1');a=p.parse_args()
    server=make_server(a.profile,a.bind)
    print('Device gateway ready on '+a.bind+':8792',flush=True)
    try:server.serve_forever()
    finally:server.server_close()
