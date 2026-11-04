"""Disposable rest-reschedule recording fixture and demo-clock helper. No Meta or other paid calls.

prepare --data <NEW_DIRECTORY> [--now 14:00]  Builds English routines, an in-progress "Start a report" run at
    "Write a working heading", and today's five reservations (Doctor call is required) through the normal APIs on temporary ports.
set --time HH:MM | advance --minutes N       Moves the clock of a running `run_integrated.py --demo-clock`.
google-ics --data <FIXTURE> --out FILE      Writes a Google Calendar export for the fixture's day (after the 21:00 day end, so the
    rest proposal and the + Add demo are unchanged). Serve it with run_integrated.py --demo-ics FILE.
Existing directories and ~/.emotion-scheduler are refused; the demo clock is unavailable in normal mode.
"""
import argparse,contextlib,json,os,socket,subprocess,threading,time,uuid
from datetime import datetime,timedelta
from pathlib import Path
from urllib.request import Request,urlopen
from server import make_server

ROOT=Path(__file__).resolve().parents[2]
QUERY="I suddenly started crying. I can't focus anymore."
BURNOUT={'title':'Burnout reset','restMinutes':180,
 'description':"For when emotions suddenly spike and you can't focus. Step away for three hours; overlapping plans are proposed for later and change only if you apply them.",
 'steps':[{'id':'phone','title':'Put your phone face down'},{'id':'water','title':'Drink a glass of water'},{'id':'rest','title':'Rest — your schedule is handled'}]}
REPORT={'title':'Start a report','description':'Make a small first draft instead of a perfect one.',
 'steps':[{'id':'open','title':'Open a blank document'},{'id':'heading','title':'Write a working heading'},{'id':'points','title':'List three key points'}]}
# (title, start, end, steps, facts): the reservations take their titles from these routines.
# facts = required / movable / deadline (HH:MM today). Unlisted facts use the reservation defaults.
SCHEDULE=[('Team sync','14:30','15:00',['Open the meeting notes','Share one update'],{}),
 ('Doctor call','15:00','15:15',['Find a quiet spot','Join the call'],{'required':True}),
 ('Budget draft','15:30','16:30',['Open last month\'s sheet','Fill in this month\'s numbers'],{'deadline':'23:59'}),
 ('Deep work block','16:00','18:00',['Close chat apps','Work on the main task'],{}),
 ('Write report section','17:30','18:30',['Reread the outline','Write one section'],{})]

def request(base,path,body=None):
    req=Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json','X-Routine-App':'local'})
    with urlopen(req,timeout=15) as response:return json.load(response)

@contextlib.contextmanager
def services(data,demo=True,provider_factory=None,demo_ics=None):
    binary=ROOT/'apps/watch-proof/executionServer/build/install/executionServer/bin/executionServer'
    if not binary.is_file():raise RuntimeError('Build :executionServer:installDist first')
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    mobile=make_server(data/'library.sqlite3',0,f'http://127.0.0.1:{port}',provider_factory=provider_factory,demo_ics=demo_ics)
    thread=threading.Thread(target=mobile.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{mobile.server_port}';env=os.environ.copy();proc=None
    try:
        if not env.get('JAVA_HOME'):env['JAVA_HOME']=subprocess.check_output(['/usr/libexec/java_home','-v','17'],text=True).strip()
        proc=subprocess.Popen([str(binary),str(port),str(data/'execution'),base,*(['--demo-clock'] if demo else [])],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for _ in range(100):
            if proc.poll() is not None:raise RuntimeError('Execution server exited')
            try:request(base,'/api/execution/context');break
            except OSError:time.sleep(.1)
        else:raise RuntimeError('Execution server readiness timeout')
        yield base
    finally:
        if proc and proc.poll() is None:
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
        mobile.shutdown();mobile.server_close();thread.join(timeout=3)

def millis(day,hhmm):return int(datetime.combine(day,datetime.strptime(hhmm,'%H:%M').time()).timestamp()*1000)
def save(base,content):return request(base,'/api/commands',{'commandId':str(uuid.uuid4()),'kind':'saveDefinition','content':content})['routine']
def command(base,value):
    out=request(base,'/api/execution/command',value)
    if not out['result']['accepted']:raise RuntimeError('Command rejected: '+out['result']['reason'])
    return out

def prepare(data,now_text='14:00'):
    data=Path(data).resolve()
    if Path.home()/'.emotion-scheduler' in [data,*data.parents]:raise ValueError('Refusing a personal data directory')
    data.mkdir(mode=0o700,parents=False,exist_ok=False)
    anchor=millis(datetime.now().date(),now_text)
    (data/'execution').mkdir();(data/'execution/demo-clock.json').write_text(json.dumps({'offsetMillis':anchor-int(time.time()*1000)}))
    (data/'demo-fixture.json').write_text(json.dumps({'fixture':'rest-reschedule-v1','nowMillis':anchor,'now':now_text,'query':QUERY},indent=2)+'\n')
    with services(data) as base:
        burnout=save(base,BURNOUT);report=save(base,REPORT);routines={}
        for title,_,_,steps,_ in SCHEDULE:routines[title]=save(base,{'title':title,'description':'','steps':[{'id':f's{i}','title':s} for i,s in enumerate(steps,1)]})
        w=request(base,'/api/execution/context')['workspace']
        command(base,{'id':str(uuid.uuid4()),'kind':'start','occurrenceId':'demo-report','expectedRevision':w['revision'],'definition':{'id':report['id'],'version':report['version'],'title':report['title'],'author':report['author']['name'],'steps':report['steps']}})
        w=request(base,'/api/execution/context')['workspace'];r=w['runs'][0]
        command(base,{'id':str(uuid.uuid4()),'kind':'complete','occurrenceId':r['id'],'expectedRevision':r['revision'],'unitId':r['currentUnitId'],'expectedFocusRevision':w['focusRevision']})
        day=datetime.fromtimestamp(anchor/1000).date()
        for title,start,end,_,facts in SCHEDULE:
            d=routines[title];key=title.lower().replace(' ','-')
            request(base,'/api/execution/reservations',{'id':key,'definitionId':d['id'],'definitionVersion':d['version'],'title':title,'startMillis':millis(day,start),'endMillis':millis(day,end),
                    'required':facts.get('required',False),'movable':facts.get('movable',True),'deadlineMillis':millis(day,facts['deadline']) if 'deadline' in facts else None})
        context=request(base,'/api/execution/context')
    run=context['workspace']['runs'][0]
    assert run['currentUnitId']=='heading' and run['status']=='running'
    return {'burnout':burnout,'reservations':len(SCHEDULE),'now':now_text}

# Google Calendar demo events (title, start, end), Asia/Seoul like a Google export. After the rest window's 21:00 day end.
GOOGLE=[('Dinner with Mina','21:00','22:00'),('Call with Dad','22:30','23:00')]
def google_ics(day,events=GOOGLE):
    d=day.strftime('%Y%m%d');stamp=datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    body=''.join(f'BEGIN:VEVENT\r\nDTSTART;TZID=Asia/Seoul:{d}T{a.replace(":","")}00\r\nDTEND;TZID=Asia/Seoul:{d}T{b.replace(":","")}00\r\n'
                 f'DTSTAMP:{stamp}\r\nUID:demo-{i}-{d}@google.com\r\nSUMMARY:{t}\r\nSTATUS:CONFIRMED\r\nEND:VEVENT\r\n' for i,(t,a,b) in enumerate(events,1))
    return ('BEGIN:VCALENDAR\r\nPRODID:-//Google Inc//Google Calendar 70.9054//EN\r\nVERSION:2.0\r\nCALSCALE:GREGORIAN\r\nX-WR-CALNAME:Demo\r\n'
            'BEGIN:VTIMEZONE\r\nTZID:Asia/Seoul\r\nBEGIN:STANDARD\r\nTZOFFSETFROM:+0900\r\nTZOFFSETTO:+0900\r\nTZNAME:KST\r\nDTSTART:19700101T000000\r\nEND:STANDARD\r\nEND:VTIMEZONE\r\n'
            +body+'END:VCALENDAR\r\n')
def fixture_day(data):return datetime.fromtimestamp(json.loads((Path(data)/'demo-fixture.json').read_text())['nowMillis']/1000).date()

def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='action',required=True)
    a=sub.add_parser('prepare');a.add_argument('--data',required=True);a.add_argument('--now',default='14:00')
    s=sub.add_parser('set');s.add_argument('--data',required=True,help='Fixture directory (its date is used)');s.add_argument('--time',required=True)
    g=sub.add_parser('google-ics');g.add_argument('--data',required=True);g.add_argument('--out',required=True)
    v=sub.add_parser('advance');v.add_argument('--minutes',type=int,required=True)
    for x in (s,v):x.add_argument('--url',default='http://127.0.0.1:8780')
    args=p.parse_args()
    if args.action=='prepare':
        out=prepare(args.data,args.now);print('Prepared disposable fixture:',Path(args.data).resolve(),'| now',out['now'],'| Burnout reset rest',out['burnout']['restMinutes'],'min')
        print('Run: python3 apps/mobile/run_integrated.py --data',Path(args.data).resolve(),'--demo-clock --demo-reset')
        return
    if args.action=='google-ics':
        Path(args.out).write_bytes(google_ics(fixture_day(args.data)).encode());print('Wrote',Path(args.out).resolve(),'|',', '.join(f'{t} {a}–{b}' for t,a,b in GOOGLE));return
    if args.action=='set':
        anchor=json.loads((Path(args.data)/'demo-fixture.json').read_text())['nowMillis']
        body={'setMillis':millis(datetime.fromtimestamp(anchor/1000).date(),args.time)}
    else:body={'advanceMinutes':args.minutes}
    out=request(args.url,'/api/execution/demo/clock',body)
    print('Server time:',datetime.fromtimestamp(out['serverNow']/1000).strftime('%Y-%m-%d %H:%M'))
if __name__=='__main__':main()
