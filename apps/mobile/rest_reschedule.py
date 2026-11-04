"""Rest-mode batch reschedule: Meta proposes, the KMP execution rules validate, the user applies.

Flow: rule preview (context) → one Meta call → validated preview with the AI suggestions.
Meta off/timeout/error keeps everything as is and returns the rule-based proposal labelled as such.
No automatic retry; a cached proposal is returned for the same rest run and schedule revision so
reopening the screen never pays twice.
"""
import json
import threading
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from store import DomainError
from localization import normalize

def hhmm(ms):return datetime.fromtimestamp(ms/1000).strftime('%H:%M')

def to_millis(day_ms,text):
    """HH:MM on the rest window's local day → epoch millis, or None when malformed."""
    try:t=datetime.strptime(text,'%H:%M').time()
    except (TypeError,ValueError):return None
    day=datetime.fromtimestamp(day_ms/1000).date()
    return int(datetime.combine(day,t).timestamp()*1000)

def meta_context(proposal):
    items=proposal['items']
    return {'restStart':hhmm(proposal['restStartMillis']),'restEnd':hhmm(proposal['restEndMillis']),'dayEnd':hhmm(proposal['dayEndMillis']),
            'targets':[{'id':i['reservation']['id'],'title':i['reservation']['title'],'start':hhmm(i['reservation']['startMillis']),
                        'end':hhmm(i['reservation']['endMillis']),
                        'minutes':(i['reservation']['endMillis']-i['reservation']['startMillis'])//60000,
                        'required':i['reservation'].get('required',False),'movable':i['reservation'].get('movable',True),
                        'deadline':hhmm(i['reservation']['deadlineMillis']) if i['reservation'].get('deadlineMillis') else ''} for i in items],
            'busy':[{'title':r['title'],'start':hhmm(r['startMillis']),'end':hhmm(r['endMillis'])}
                    for r in proposal['fixed'] if r['endMillis']>proposal['restStartMillis'] and r['startMillis']<proposal['dayEndMillis']]}

def suggestions(raw,proposal):
    """Shape check only. Every rule is enforced by the KMP validator, so a bad time stays visible as 'needs check'."""
    if not isinstance(raw,dict) or not isinstance(raw.get('items'),list):raise DomainError('META_INVALID','추천 내용을 확인할 수 없어요. 다시 시도해 주세요.',502)
    out=[]
    for x in raw['items'][:50]:
        if not isinstance(x,dict) or not isinstance(x.get('id'),str) or not 1<=len(x['id'])<=100:continue
        action=x.get('action') if x.get('action') in ('move','skip_this_time','keep','later') else 'invalid'
        start=to_millis(proposal['restStartMillis'],x.get('newStart')) if action=='move' else None
        reason=x.get('reason') if isinstance(x.get('reason'),str) else ''
        out.append({'reservationId':x['id'],'action':action,'newStartMillis':start,'reason':reason[:300],'source':'ai'})
    return out

class RestRescheduleService:
    def __init__(self,execution_url,provider_factory=None):
        self.execution_url=execution_url;self.provider_factory=provider_factory
        self.lock=threading.Lock();self.cache={};self.last_metrics=[]

    def execution(self,path,body):
        req=Request(self.execution_url+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','X-Routine-App':'local'})
        try:
            with urlopen(req,timeout=5) as response:return json.load(response)
        except HTTPError as e:
            if e.code==400:raise DomainError('INVALID','휴식 루틴을 먼저 시작해 주세요.',400) from None
            raise DomainError('EXECUTION_UNAVAILABLE','실행 연결을 확인해 주세요. 같은 요청으로 다시 확인할 수 있습니다.',503) from None
        except (URLError,TimeoutError,OSError,ValueError):
            raise DomainError('EXECUTION_UNAVAILABLE','실행 연결을 확인해 주세요. 같은 요청으로 다시 확인할 수 있습니다.',503) from None

    def propose(self,body):
        if not isinstance(body,dict) or not isinstance(body.get('occurrenceId'),str) or type(body.get('restMinutes')) is not int:
            raise DomainError('INVALID','휴식 루틴을 확인해 주세요.')
        base={'occurrenceId':body['occurrenceId'],'restMinutes':body['restMinutes']}
        if isinstance(body.get('dayEnd'),str):base['dayEnd']=body['dayEnd']
        if not self.lock.acquire(blocking=False):
            raise DomainError('RECOMMENDATION_BUSY','조정안을 준비하고 있어요. 잠시 후 다시 확인해 주세요.',409)
        try:
            rule=self.execution('/reschedule/preview',base)
            key=json.dumps([base,rule['proposal']['expectedRevision'],normalize(body.get('language','en'))],sort_keys=True)
            # An explicit user retry (retryAi) is the only way to call Meta again after a failure.
            if key in self.cache and not (body.get('retryAi') is True and self.cache[key]['ai']['status']=='error'):return self.cache[key]
            result={'proposal':rule['proposal'],'rejected':[],'ai':{'status':'off'}}
            if rule['proposal']['items'] and self.provider_factory:
                provider=None
                try:
                    provider=self.provider_factory();provider.language=normalize(body.get('language','en'))
                    raw=provider.reschedule(meta_context(rule['proposal']))
                    validated=self.execution('/reschedule/preview',dict(base,suggestions=suggestions(raw,rule['proposal'])))
                    if validated['proposal']['expectedRevision']!=rule['proposal']['expectedRevision']:
                        raise DomainError('SEARCH_STALE','일정이 그사이 바뀌었어요. 다시 확인해 주세요.',409)
                    result={'proposal':validated['proposal'],'rejected':validated['rejected'],'ai':{'status':'ok'}}
                except DomainError as e:
                    if e.code=='EXECUTION_UNAVAILABLE':raise
                    # Keep input and state; show the rule-based plan, labelled. Never retry automatically.
                    result['ai']={'status':'error','code':e.code}
                except Exception:
                    # Unexpected provider failure: same safe fallback, no detail kept.
                    result['ai']={'status':'error','code':'META_UNAVAILABLE'}
                finally:
                    self.last_metrics=list(getattr(provider,'metrics',[]) or [])
            self.cache[key]=result
            return result
        finally:self.lock.release()
