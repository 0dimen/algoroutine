"""Isolated test server: hold one READ response, never alter its content.
Local ports 8780 mobile, 8792 engine, 8791 test proxy. Test controls exist only here.
"""
import argparse,json,os,subprocess,sys,threading,time
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.request import Request,urlopen
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'apps/mobile'))
from server import make_server
lock=threading.Lock();offline=False;armed=False;captured=threading.Event();release=threading.Event()
class Proxy(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):self.handle_request()
 def do_POST(self):self.handle_request()
 def handle_request(self):
  global armed,offline
  if self.path=='/test/offline':offline=True;return self.reply(b'{}')
  if self.path=='/test/online':offline=False;return self.reply(b'{}')
  if offline and not self.path.startswith('/test/'):
   self.send_response(503);self.send_header('Content-Length','0');self.end_headers();return
  if self.path=='/test/arm':
   with lock:armed=True;captured.clear();release.clear()
   return self.reply(b'{}')
  if self.path=='/test/status':return self.reply(json.dumps({'captured':captured.is_set()}).encode())
  if self.path=='/test/release':release.set();return self.reply(b'{}')
  body=self.rfile.read(int(self.headers.get('Content-Length',0))) if self.command=='POST' else None
  with urlopen(Request('http://127.0.0.1:8792'+self.path,data=body,headers={'Content-Type':'application/json','X-Routine-App':'local'}),timeout=5) as response:data=response.read()
  should_hold=False
  if self.path=='/context':
   with lock:
    if armed:armed=False;should_hold=True
  if should_hold:captured.set();release.wait(8)
  self.reply(data)
 def reply(self,data):
  try:self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
  except (BrokenPipeError,ConnectionResetError):pass

def main():
 p=argparse.ArgumentParser();p.add_argument('--data',required=True);a=p.parse_args();data=Path(a.data);data.mkdir(parents=True,exist_ok=True)
 mobile=make_server(data/'library.sqlite3',8780,'http://127.0.0.1:8792')
 env=dict(os.environ,JAVA_HOME=subprocess.check_output(['/usr/libexec/java_home','-v','17'],text=True).strip())
 engine=subprocess.Popen([str(ROOT/'apps/watch-proof/executionServer/build/install/executionServer/bin/executionServer'),'8792',str(data/'execution'),'http://127.0.0.1:8780'],env=env)
 threading.Thread(target=mobile.serve_forever,daemon=True).start();proxy=ThreadingHTTPServer(('127.0.0.1',8791),Proxy)
 try:print('Isolated delayed-read fixture on 8780/8791/8792',flush=True);proxy.serve_forever()
 except KeyboardInterrupt:pass
 finally:release.set();proxy.server_close();mobile.shutdown();mobile.server_close();engine.terminate();engine.wait(timeout=10)
if __name__=='__main__':main()
