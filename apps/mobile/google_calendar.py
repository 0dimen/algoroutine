"""Read-only Google Calendar import from the calendar's secret iCal address (or posted .ics text). Standard library only.

Today's timed events (server clock, so the demo clock is respected) become plain schedules that are Required (time cannot
change). The reservation id is "gcal-" + a hash of the event UID and its occurrence, so a re-import never duplicates.
Supported: DTSTART/DTEND/DURATION with TZID, UTC (Z) or floating times; RRULE FREQ=DAILY/WEEKLY (INTERVAL, COUNT, UNTIL,
BYDAY), EXDATE, RECURRENCE-ID overrides, STATUS:CANCELLED. All-day events are not added (counted). Other repeat rules add
only their first occurrence (counted as unsupportedRepeat).
The iCal address is a secret: it is never logged, never returned and never sent to Meta; it is kept only in the local data dir.
"""
import calendar,hashlib,json,os,re,ssl,subprocess,sys,time
from datetime import date,datetime,timedelta
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
from store import DomainError

MAX_BYTES=2_000_000;ID_PREFIX='gcal-';DAYS=['MO','TU','WE','TH','FR','SA','SU'];ZONEINFO=Path('/usr/share/zoneinfo')

def unfold(text):
    out=[]
    for line in text.replace('\r\n','\n').replace('\r','\n').split('\n'):
        if line[:1] in (' ','\t') and out:out[-1]+=line[1:]
        elif line:out.append(line)
    return out

def prop(line):
    """NAME;P=V;P2="a:b":value -> (NAME, {P:V}, value). Colons inside quoted parameter values are kept."""
    quoted=False
    for i,ch in enumerate(line):
        if ch=='"':quoted=not quoted
        elif ch==':' and not quoted:head,value=line[:i],line[i+1:];break
    else:return None
    parts=head.split(';');params={}
    for p in parts[1:]:
        k,_,v=p.partition('=');params[k.upper()]=v.strip('"')
    return parts[0].upper(),params,value

def text_value(v):return re.sub(r'\\(.)',lambda m:'\n' if m.group(1) in 'nN' else m.group(1),v).strip()

def parse(text):
    """Top-level VEVENTs only (VALARM etc. inside an event are ignored). Each value is (params, raw) or a list for EXDATE."""
    events=[];stack=[];cur=None
    for line in unfold(text):
        p=prop(line)
        if not p:continue
        name,params,value=p
        if name=='BEGIN':
            stack.append(value.upper())
            if stack==['VCALENDAR','VEVENT'] or stack==['VEVENT']:cur={'EXDATE':[]}
        elif name=='END':
            if cur is not None and stack and stack[-1]=='VEVENT' and len(stack)<=2:events.append(cur);cur=None
            if stack:stack.pop()
        elif cur is not None and stack and stack[-1]=='VEVENT':
            if name=='EXDATE':cur['EXDATE']+=[(params,v) for v in value.split(',') if v]
            else:cur[name]=(params,value)
    return events

def when(params,value):
    """-> ('date', date) | (zone, naive datetime) with zone 'UTC', a TZID, or None (floating = local)."""
    value=value.strip()
    if params.get('VALUE','').upper()=='DATE' or re.fullmatch(r'\d{8}',value):return 'date',datetime.strptime(value[:8],'%Y%m%d').date()
    m=re.fullmatch(r'(\d{8}T\d{6})(Z?)',value)
    if not m:raise ValueError('bad date-time')
    naive=datetime.strptime(m.group(1),'%Y%m%dT%H%M%S')
    return ('UTC' if m.group(2) else params.get('TZID') or None),naive

def duration(value):
    m=re.fullmatch(r'([+-])?P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?',value.strip())
    if not m:raise ValueError('bad duration')
    sign=-1 if m.group(1)=='-' else 1;w,d,h,mi,s=(int(x or 0) for x in m.groups()[1:])
    return sign*timedelta(weeks=w,days=d,hours=h,minutes=mi,seconds=s)

def valid_zone(tzid):
    return bool(tzid) and re.fullmatch(r'[A-Za-z0-9_+\-]+(/[A-Za-z0-9_+\-]+)*',tzid) is not None and (ZONEINFO/tzid).is_file()

_ZONE_SCRIPT=('import json,os,sys,time\nout=[]\nfor z,t in json.load(sys.stdin):\n os.environ["TZ"]=z;time.tzset()\n'
              ' out.append(int(time.mktime(tuple(t)+(0,0,-1))))\nprint(json.dumps(out))')

def epochs(pairs):
    """[(zone, naive)] -> epoch seconds. Named zones go through the OS tz database in a child process (Python 3.8 has no
    zoneinfo; TZ is process-global, so it is never changed in this threaded server). Unknown zones are treated as local."""
    out=[None]*len(pairs);named=[]
    for i,(zone,naive) in enumerate(pairs):
        if zone=='UTC':out[i]=calendar.timegm(naive.timetuple())
        elif valid_zone(zone):named.append(i)
        else:out[i]=int(time.mktime(naive.timetuple()))
    if named:
        job=json.dumps([[pairs[i][0],list(pairs[i][1].timetuple())[:6]] for i in named])
        res=subprocess.run([sys.executable,'-c',_ZONE_SCRIPT],input=job,capture_output=True,text=True,timeout=10,env={'PATH':os.environ.get('PATH','')})
        if res.returncode!=0:raise DomainError('CALENDAR_INVALID','캘린더 시간대를 읽을 수 없어요.',422)
        for i,v in zip(named,json.loads(res.stdout)):out[i]=v
    return out

def rule(text):
    r={}
    for part in text.split(';'):
        k,_,v=part.partition('=');r[k.upper()]=v
    return r

def expand(start,rr,limit):
    """Occurrence starts (naive, event wall time) from DTSTART up to limit, for FREQ=DAILY/WEEKLY. None if unsupported."""
    freq=rr.get('FREQ','').upper();interval=max(1,int(rr.get('INTERVAL') or 1));count=int(rr['COUNT']) if rr.get('COUNT') else None
    unsupported={'BYMONTH','BYMONTHDAY','BYYEARDAY','BYWEEKNO','BYSETPOS','BYHOUR','BYMINUTE','BYSECOND'}&set(rr)
    byday=[d[-2:].upper() for d in rr.get('BYDAY','').split(',') if d]
    if freq not in ('DAILY','WEEKLY') or unsupported or any(not re.fullmatch(r'(MO|TU|WE|TH|FR|SA|SU)',d) for d in byday) or any(re.search(r'\d',d) for d in rr.get('BYDAY','').split(',')):return None
    days={DAYS.index(d) for d in byday};out=[]
    if freq=='DAILY':
        k=0
        while True:
            t=start+timedelta(days=k*interval)
            if t>limit or (count is not None and len(out)>=count) or k>200000:break
            if not days or t.weekday() in days:out.append(t)
            k+=1
    else:
        days=days or {start.weekday()};week0=start-timedelta(days=start.weekday());k=0
        while True:
            base=week0+timedelta(weeks=k*interval)
            if base>limit or (count is not None and len(out)>=count) or k>50000:break
            for wd in sorted(days):
                t=base+timedelta(days=wd)
                if t<start or t>limit:continue
                if count is not None and len(out)>=count:break
                out.append(t)
            k+=1
    return out

def occurrences(text,day_start_ms,day_end_ms):
    """Timed occurrences whose start is in [day_start_ms, day_end_ms). -> (items, counts)."""
    counts={'allDay':0,'unsupportedRepeat':0,'cancelled':0,'invalid':0}
    events=parse(text);overrides={};singles=[]
    for e in events:
        if 'DTSTART' not in e or 'UID' not in e:counts['invalid']+=1;continue
        if 'RECURRENCE-ID' in e:overrides.setdefault(e['UID'][1].strip(),[]).append(e)
        else:singles.append(e)
    limit=datetime.fromtimestamp(day_end_ms/1000)+timedelta(days=2)
    cands=[]  # (uid, event, zone, naive start, length, original zone/naive for the occurrence key)
    for e in singles:
        try:
            zone,start=when(*e['DTSTART'])
            if zone=='date':counts['allDay']+=1;continue
            end=when(*e['DTEND']) if 'DTEND' in e else None
            if end and end[0]=='date':counts['allDay']+=1;continue
            length=end[1]-start if end else duration(e['DURATION'][1]) if 'DURATION' in e else timedelta(0)
            starts=[start]
            if 'RRULE' in e:
                rr=rule(e['RRULE'][1]);got=expand(start,rr,limit)
                if got is None:counts['unsupportedRepeat']+=1
                else:
                    starts=got
                    if rr.get('UNTIL'):e['_until']=when({},rr['UNTIL'])
            for s in starts:cands.append((e['UID'][1].strip(),e,zone,s,length))
        except (ValueError,KeyError):counts['invalid']+=1
    # One batch conversion: occurrence starts, ends, UNTIL, EXDATEs and RECURRENCE-IDs.
    pairs=[]
    for _,e,zone,s,length in cands:pairs+=[(zone,s),(zone,s+length)]
    extra=[]
    for e in singles:
        u=e.get('_until')
        if u and u[0]!='date':extra.append(('until',id(e),u))
        elif u:extra.append(('until',id(e),(when(*e['DTSTART'])[0],datetime.combine(u[1],datetime.max.time().replace(microsecond=0)))))
        for p,v in e['EXDATE']:
            try:
                z,n=when(p,v)
                if z!='date':extra.append(('ex',id(e),(z,n)))
            except ValueError:pass
    over=[]
    for uid,items in overrides.items():
        for e in items:
            try:
                rz,rn=when(*e['RECURRENCE-ID']);z,s=when(*e['DTSTART'])
                if rz=='date' or z=='date':counts['allDay']+=1;continue
                length=when(*e['DTEND'])[1]-s if 'DTEND' in e else duration(e['DURATION'][1]) if 'DURATION' in e else timedelta(0)
                over.append((uid,e,z,s,length));extra.append(('rid',len(over)-1,(rz,rn)))
            except (ValueError,KeyError):counts['invalid']+=1
    for _,e,z,s,length in over:pairs+=[(z,s),(z,s+length)]
    secs=epochs(pairs+[x[2] for x in extra])
    n=len(cands)*2;base=secs[:n];ov=secs[n:n+len(over)*2];ex=secs[n+len(over)*2:]
    until={};exdates={};rids={}
    for (kind,key,_),v in zip(extra,ex):
        if kind=='until':until[key]=v
        elif kind=='ex':exdates.setdefault(key,set()).add(v)
        else:rids[key]=v
    replaced={}
    for i,(uid,e,_,_,_) in enumerate(over):replaced[(uid,rids[i])]=(e,ov[2*i],ov[2*i+1])
    items={}
    def add(uid,e,occ,start,end):
        if e.get('STATUS',({},''))[1].strip().upper()=='CANCELLED':counts['cancelled']+=1;return
        if not day_start_ms<=start*1000<day_end_ms or end<=start:return
        title=' '.join(text_value(e['SUMMARY'][1]).split()) if 'SUMMARY' in e else ''
        key=ID_PREFIX+hashlib.sha256((uid+'|'+str(occ)).encode()).hexdigest()[:20]
        items[key]={'id':key,'uid':uid,'occurrence':occ,'title':(title or '(No title)')[:120],'startMillis':start*1000,'endMillis':end*1000}
    for i,(uid,e,_,_,_) in enumerate(cands):
        s,end=base[2*i],base[2*i+1]
        if id(e) in until and s>until[id(e)]:continue
        if s in exdates.get(id(e),()):continue
        if (uid,s) in replaced:
            oe,os_,oend=replaced.pop((uid,s));add(uid,oe,s,os_,oend)
        else:add(uid,e,s if 'RRULE' in e else 0,s,end)  # a single event keeps one id when its time changes
    for (uid,occ),(oe,os_,oend) in replaced.items():add(uid,oe,occ,os_,oend)  # moved instance whose original was outside the expansion
    return sorted(items.values(),key=lambda x:(x['startMillis'],x['title'])),counts

def fetch(url,demo_ics=None):
    """The secret address: https (webcal accepted). The demo file only when the app runs with --demo-ics."""
    if not isinstance(url,str) or not 8<=len(url)<=2000:raise DomainError('CALENDAR_URL','iCal 주소를 확인해 주세요.')
    url=url.strip();parts=urlsplit(url)
    if demo_ics and parts.scheme=='http' and parts.hostname in ('127.0.0.1','localhost') and parts.path=='/demo/google.ics':
        return Path(demo_ics).read_text(encoding='utf-8')
    if parts.scheme=='webcal':url='https'+url[len('webcal'):];parts=urlsplit(url)
    if parts.scheme!='https' or not parts.hostname:raise DomainError('CALENDAR_URL','iCal 주소를 확인해 주세요.')
    ctx=ssl.create_default_context()
    if not ssl.get_default_verify_paths().cafile and Path('/etc/ssl/cert.pem').is_file():ctx.load_verify_locations('/etc/ssl/cert.pem')
    try:
        with urlopen(Request(url,headers={'User-Agent':'AlgoRoutine-local'}),timeout=15,context=ctx) as r:raw=r.read(MAX_BYTES+1)
    except (HTTPError,URLError,TimeoutError,OSError,ValueError):
        # Never echo the address or the library's message (it can contain the address).
        raise DomainError('CALENDAR_FETCH','캘린더를 가져오지 못했어요. 주소와 연결을 확인해 주세요.',502) from None
    if len(raw)>MAX_BYTES:raise DomainError('CALENDAR_INVALID','캘린더가 너무 커요.',422)
    return raw.decode('utf-8','replace')

class GoogleCalendarImport:
    def __init__(self,data_dir,execution_url,demo_ics=None):
        self.file=Path(data_dir)/'google-calendar.json';self.execution_url=execution_url;self.demo_ics=demo_ics

    def _saved(self):
        try:return json.loads(self.file.read_text())
        except (OSError,ValueError):return {}

    def _save(self,value):
        tmp=self.file.with_suffix('.tmp');fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,'w') as f:json.dump(value,f)
        os.replace(tmp,self.file)

    def status(self):return {'saved':bool(self._saved().get('url'))}

    def execution(self,path,body=None):
        req=Request(self.execution_url+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json','X-Routine-App':'local'})
        with urlopen(req,timeout=5) as response:return json.load(response)

    def run(self,body):
        url=body.get('url');ics=body.get('ics')
        saved=self._saved()
        if isinstance(ics,str) and ics.strip():text=ics
        else:
            if not (isinstance(url,str) and url.strip()):url=saved.get('url')
            if not url:raise DomainError('CALENDAR_URL','iCal 주소를 확인해 주세요.')
            text=fetch(url,self.demo_ics)
        if 'BEGIN:VCALENDAR' not in text.upper():raise DomainError('CALENDAR_INVALID','iCal 형식이 아니에요. "iCal 형식의 비밀 주소"를 붙여 넣어 주세요.',422)
        try:now=self.execution('/context')['serverNow']
        except (HTTPError,URLError,TimeoutError,OSError,ValueError,KeyError):raise DomainError('EXECUTION_UNAVAILABLE','실행 연결을 확인해 주세요. 같은 요청으로 다시 확인할 수 있습니다.',503) from None
        day=datetime.fromtimestamp(now/1000).date()
        start=int(datetime.combine(day,datetime.min.time()).timestamp()*1000);end=int(datetime.combine(day+timedelta(days=1),datetime.min.time()).timestamp()*1000)
        items,counts=occurrences(text,start,end)
        existing={r['id']:r for r in self.execution('/reservations')}
        out={'added':0,'unchanged':0,'changed':0,'past':0,**counts,'ids':[]}
        events=dict(saved.get('events',{}))
        for x in items:
            if x['endMillis']<=now:out['past']+=1;continue
            body={'id':x['id'],'kind':'schedule','definitionId':'schedule','definitionVersion':1,'title':x['title'],'startMillis':x['startMillis'],
                  'endMillis':x['endMillis'],'required':True,'movable':False,'deadlineMillis':None}
            old=existing.get(x['id'])
            if old is not None and (old['title'],old['startMillis'],old['endMillis'])!=(x['title'],x['startMillis'],x['endMillis']):
                # Same Google event, new time or title (or moved by an applied rest plan): the execution store has no update yet.
                out['changed']+=1;continue
            try:self.execution('/reservations',body)
            except HTTPError:out['invalid']+=1;continue
            except (URLError,TimeoutError,OSError,ValueError):raise DomainError('EXECUTION_UNAVAILABLE','실행 연결을 확인해 주세요. 같은 요청으로 다시 확인할 수 있습니다.',503) from None
            out['unchanged' if old is not None else 'added']+=1;out['ids'].append(x['id'])
            events[x['id']]={'source':'Google Calendar','uid':x['uid'][:500],'occurrence':x['occurrence']}
        value={'events':events}
        if isinstance(url,str) and url.strip() and not (isinstance(ics,str) and ics.strip()):value['url']=url.strip()
        elif saved.get('url'):value['url']=saved['url']
        self._save(value)
        return out
