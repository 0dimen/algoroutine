"""Loopback-only, single-user development app; not a hosted multi-user service."""
import argparse
import json
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from store import Store, DomainError, CATALOG
from search import search

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Do not log routine text, queries or draft contents.

    def respond(self, status, data, content_type='application/json; charset=utf-8'):
        if isinstance(data,dict) and isinstance(data.get('error'),dict):
            from localization import translate
            data['error']['message']=translate(data['error']['message'],self.headers.get('X-Routine-Language','en'))
        raw = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode()
        try:
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError):
            # Client cancelled/navigation closed the response. Never retry the
            # model or roll back an already accepted command due to delivery.
            self.close_connection=True


    def do_GET(self):
        self.handle_request(False)

    def do_POST(self):
        self.handle_request(True)

    def handle_request(self, write):
        try:
            allowed = {'127.0.0.1:'+str(self.server.server_port), 'localhost:'+str(self.server.server_port)}
            host = self.headers.get('Host','')
            if host not in allowed:
                raise DomainError('FORBIDDEN','이 개발 앱은 로컬에서만 사용할 수 있습니다.',403)
            path = urlsplit(self.path).path
            if not write and path in ['/','/app.js','/style.css','/tokens.css','/voice.js','/voice-worklet.js','/i18n.js','/messages.js']:
                f = Path(__file__).parent/'web'/('index.html' if path=='/' else path[1:])
                mime = {'html':'text/html','js':'text/javascript','css':'text/css'}[f.suffix[1:]]
                return self.respond(200,f.read_bytes(),mime+'; charset=utf-8')
            store = self.server.store
            if write:
                origin = self.headers.get('Origin')
                if self.headers.get('X-Routine-App') != 'local' or (origin and origin != 'http://'+host):
                    raise DomainError('FORBIDDEN','같은 앱에서 다시 요청해 주세요.',403)
                length = int(self.headers.get('Content-Length','0'))
                if not 0 < length <= 150000 or not self.headers.get('Content-Type','').startswith('application/json'):
                    raise DomainError('INVALID','요청 크기와 형식을 확인해 주세요.')
                body = json.loads(self.rfile.read(length))
                if not isinstance(body,dict):
                    raise DomainError('INVALID','요청 형식을 확인해 주세요.')
                if path.startswith('/api/voice/'):
                    if self.server.voice is None:
                        raise DomainError('VOICE_UNAVAILABLE','음성 연결이 준비되지 않았어요. 글로 입력해 주세요.',503)
                    return self.respond(200,self.server.voice.action(path.rsplit('/',1)[-1],body))
                if path in ['/api/execution/command','/api/execution/reservations','/api/execution/reschedule/apply','/api/execution/demo/clock']:
                    return self.execution(path,body)
                if path == '/api/rest/proposal':
                    return self.respond(200,self.server.rest.propose(body))
                if path == '/api/recommend':
                    if self.server.recommendations is None:
                        raise DomainError('META_DISABLED','AI 추천 연결이 준비되지 않았어요.',503)
                    return self.respond(200,self.server.recommendations.recommend(body.get('query'),body.get('language','en')))
                if path == '/api/search':
                    return self.respond(200,search(store,body.get('query')))
                if path == '/api/commands':
                    return self.respond(200,store.command(body))
                if path == '/api/drafts':
                    return self.respond(200,store.save_draft(body.get('key'),body.get('expectedRevision'),body.get('content')))
            else:
                if path in ['/api/execution/context','/api/execution/events','/api/execution/reservations','/api/execution/demo/clock']:
                    return self.execution(path)
                q = parse_qs(urlsplit(self.path).query)
                if path == '/api/capabilities':
                    return self.respond(200,{'meta':self.server.recommendations is not None,'voice':self.server.voice is not None})
                if path == '/api/library':
                    return self.respond(200,store.library())
                if path == '/api/catalog':
                    return self.respond(200,{'items':CATALOG})
                if path == '/api/routine':
                    definition_id=q.get('id',[''])[0];version=int(q['version'][0]) if 'version' in q else None
                    catalog=next((r for r in CATALOG if r['id']==definition_id and (version is None or version==r['version'])),None)
                    return self.respond(200,catalog if catalog is not None else store.version(definition_id,version))
                if path == '/api/draft':
                    return self.respond(200,store.draft(q.get('key',['new'])[0]))
                if path == '/api/command':
                    return self.respond(200,store.command_result(q.get('id',[''])[0]))
            raise DomainError('NOT_FOUND','화면을 찾을 수 없습니다.',404)
        except DomainError as e:
            self.respond(e.status,{'error':{'code':e.code,'message':e.message}})
        except (ValueError,TypeError):
            self.respond(400,{'error':{'code':'INVALID','message':'입력 형식을 확인해 주세요.'}})
        except sqlite3.Error:
            self.respond(503,{'error':{'code':'STORAGE_UNAVAILABLE','message':'저장소를 사용할 수 없습니다. 입력을 유지하고 다시 시도해 주세요.'}})

    def execution(self,path,body=None):
        endpoint=self.server.execution_url+path[len('/api/execution'):]
        req=Request(endpoint,data=json.dumps(body).encode() if body is not None else None,
                    headers={'Content-Type':'application/json','X-Routine-App':'local'})
        try:
            with urlopen(req,timeout=5) as response:
                return self.respond(200,json.load(response))
        except HTTPError as e:
            return self.respond(e.code,json.load(e))
        except (URLError,TimeoutError,OSError,ValueError):
            raise DomainError('EXECUTION_UNAVAILABLE','실행 연결을 확인해 주세요. 같은 요청으로 다시 확인할 수 있습니다.',503)

def make_server(path,port=8780,execution_url='http://127.0.0.1:8791',provider_factory=None,voice_factory=None):
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    server.store=Store(path)
    from recommendation_service import RecommendationService
    server.recommendations=RecommendationService(server.store,provider_factory) if provider_factory else None
    from voice import VoiceManager
    server.voice=VoiceManager(voice_factory) if voice_factory else None
    server.execution_url=execution_url
    from rest_reschedule import RestRescheduleService
    server.rest=RestRescheduleService(execution_url,provider_factory)
    return server

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8780);parser.add_argument('--db',default=str(Path.home()/'.emotion-scheduler'/'library.sqlite3'))
    parser.add_argument('--meta',action='store_true',help='Enable paid Meta recommendations using the local key')
    args=parser.parse_args();Path(args.db).parent.mkdir(parents=True,exist_ok=True)
    from voice import meta_voice_session
    from meta_provider import MetaProvider
    server=make_server(args.db,args.port,provider_factory=MetaProvider.local if args.meta else None,voice_factory=meta_voice_session if args.meta else None)
    print('Local app: http://127.0.0.1:'+str(server.server_port),flush=True)
    server.serve_forever()
