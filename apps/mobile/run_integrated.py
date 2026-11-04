"""Start the loopback mobile + KMP integration profile; never a public server."""
import argparse,json,os,subprocess,time
from pathlib import Path
from server import make_server

DEFAULT_DATA=Path.home()/'.emotion-scheduler/integration'
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--data',default=str(DEFAULT_DATA))
 parser.add_argument('--meta',action='store_true',help='Enable Meta recommendations')
 parser.add_argument('--demo-clock',action='store_true',help='Recording only: allow shifting the server clock. Requires a rest_demo.py fixture directory')
 parser.add_argument('--demo-reset',action='store_true',help='With --demo-clock: move the server clock back to the fixture start time')
 args=parser.parse_args();data=Path(args.data).resolve()
 if args.demo_reset and not args.demo_clock:parser.error('--demo-reset requires --demo-clock')
 if args.demo_clock:
  # Never on personal data: only a disposable directory created by rest_demo.py prepare.
  marker=data/'demo-fixture.json'
  if data==DEFAULT_DATA.resolve() or Path.home()/'.emotion-scheduler' in [data,*data.parents] or not marker.is_file():
   parser.error('--demo-clock only works on a disposable rest_demo.py fixture directory')
  if args.demo_reset:
   anchor=json.loads(marker.read_text())['nowMillis']
   (data/'execution/demo-clock.json').write_text(json.dumps({'offsetMillis':anchor-int(time.time()*1000)}))
 data.mkdir(parents=True,exist_ok=True)
 binary=Path(__file__).resolve().parents[1]/'watch-proof/executionServer/build/install/executionServer/bin/executionServer'
 if not binary.exists():parser.error('Build :executionServer:installDist first.')
 env=os.environ.copy()
 if 'JAVA_HOME' not in env:env['JAVA_HOME']=subprocess.check_output(['/usr/libexec/java_home','-v','17'],text=True).strip()
 from voice import meta_voice_session
 from meta_provider import MetaProvider
 server=make_server(data/'library.sqlite3',8780,provider_factory=MetaProvider.local if args.meta else None,voice_factory=meta_voice_session if args.meta else None)
 process=subprocess.Popen([str(binary),'8791',str(data/'execution'),'http://127.0.0.1:8780',*(['--demo-clock'] if args.demo_clock else [])],env=env)
 try:
  print('Mobile: http://127.0.0.1:8780 | local KMP: 8791'+(' | DEMO CLOCK' if args.demo_clock else ''),flush=True)
  server.serve_forever()
 except KeyboardInterrupt:pass
 finally:
  if server.voice:server.voice.close()
  server.server_close();process.terminate()
  try:process.wait(timeout=5)
  except subprocess.TimeoutExpired:process.kill();process.wait()
if __name__=='__main__':main()
