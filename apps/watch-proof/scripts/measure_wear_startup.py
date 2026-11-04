"""Measure a small emulator sample; never infer real-device SLA or p95.
Requires a running local service and an active disposable execution fixture.
"""
import argparse,json,os,re,subprocess,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--serial',default='emulator-5560');p.add_argument('--samples',type=int,default=3);p.add_argument('--output',required=True);p.add_argument('--package',default='app.algoroutine.watchproof');p.add_argument('--sequential',action='store_true',help='Local integration control: wait for composition before first request');a=p.parse_args();assert 1<=a.samples<=10
adb=str(Path(os.environ.get('ANDROID_HOME',str(Path.home()/'Library/Android/sdk')))/'platform-tools/adb')
def run(*args):return subprocess.check_output([adb,'-s',a.serial,*args],text=True,timeout=30)
package=a.package
assert package in ('app.algoroutine.watchproof','app.algoroutine.watchproof.benchmark')
def framework():return [line for line in run('logcat','-d','-s','ActivityTaskManager:I','*:S').splitlines() if ('Fully drawn '+package+'/') in line]
rows=[]
for index in range(a.samples):
 before=set(framework());run('shell','am','force-stop',package)
 t=time.monotonic();launch=run('shell','am','start','-W','-n',package+'/app.algoroutine.wear.MainActivity','--ez','demo_server','true','--ez','parallel_initial_load','false' if a.sequential else 'true');wall=round((time.monotonic()-t)*1000)
 pid=run('shell','pidof',package).strip();assert pid,'App process unavailable'
 logs=''
 for _ in range(20):
  logs=run('logcat','-d','--pid',pid,'-s','RoutineStartup:I','RoutineNetwork:I','*:S')
  if 'remote_data_ready_ms=' in logs:break
  time.sleep(.25)
 data=re.search(r'remote_data_ready_ms=(\d+)',logs);network=re.search(r'read_ms=(\d+)',logs);initial=re.search(r'TotalTime: (\d+)',launch)
 drawn=[line for line in framework() if line not in before]
 rows.append({'sample':index+1,'pid':pid,'ttidMs':int(initial[1]) if initial else None,'onCreateToDataMs':int(data[1]) if data else None,'firstReadMs':int(network[1]) if network else None,'adbLaunchWallMs':wall,'fullyDrawnEvidence':drawn,'launchEvidence':launch,'appTimingEvidence':logs})
 Path(a.output).write_text(json.dumps({'environment':'Wear emulator, '+package+', process cold starts, local server; no physical-device SLA claim','requestScheduling':'sequential' if a.sequential else 'overlapped','samples':rows},ensure_ascii=False,indent=2)+'\n')
 print({k:v for k,v in rows[-1].items() if k in ['sample','ttidMs','onCreateToDataMs','firstReadMs']},flush=True)
