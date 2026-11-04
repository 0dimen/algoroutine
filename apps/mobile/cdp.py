"""Local Chrome DevTools verification; no external services or dependencies."""
import base64, json, os, socket, struct, time, urllib.request
from pathlib import Path
class CDP:
    def __init__(self):
        tabs=json.load(urllib.request.urlopen('http://127.0.0.1:9333/json'))
        from urllib.parse import urlparse
        u=urlparse(next(t['webSocketDebuggerUrl'] for t in tabs if t['type']=='page'))
        self.s=socket.create_connection((u.hostname,u.port));self.s.settimeout(10);self.id=0
        key=base64.b64encode(os.urandom(16)).decode()
        self.s.sendall(('GET '+u.path+' HTTP/1.1\r\nHost: '+u.netloc+'\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: '+key+'\r\nSec-WebSocket-Version: 13\r\n\r\n').encode())
        data=b''
        while b'\r\n\r\n' not in data:data+=self.s.recv(1)
        assert b'101' in data,data
    def read(self,n):
        data=b''
        while len(data)<n:data+=self.s.recv(n-len(data))
        return data
    def call(self,method,params=None):
        self.id+=1;raw=json.dumps({'id':self.id,'method':method,'params':params or {}}).encode();mask=os.urandom(4);n=len(raw)
        head=bytes([0x81,0x80|(n if n<126 else 126 if n<65536 else 127)])
        if n>=126:head+=struct.pack('!H' if n<65536 else '!Q',n)
        self.s.sendall(head+mask+bytes(v^mask[i%4] for i,v in enumerate(raw)))
        while True:
            h=self.read(2);size=h[1]&127
            if size==126:size=struct.unpack('!H',self.read(2))[0]
            elif size==127:size=struct.unpack('!Q',self.read(8))[0]
            key=self.read(4) if h[1]&128 else None;payload=self.read(size)
            if key:payload=bytes(v^key[i%4] for i,v in enumerate(payload))
            if h[0]&15!=1:continue
            message=json.loads(payload)
            if message.get('id')==self.id:
                if 'error' in message:raise RuntimeError(message['error'])
                return message.get('result',{})
    def js(self,expression):
        r=self.call('Runtime.evaluate',{'expression':expression,'returnByValue':True,'awaitPromise':True})
        if 'exceptionDetails' in r:raise RuntimeError(r['exceptionDetails'])
        return r['result'].get('value')
    def shot(self,path):
        r=self.call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False});Path(path).write_bytes(base64.b64decode(r['data']))

