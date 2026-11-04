"""Rest routine → AI batch proposal (mock Meta) → validated defaults → one Apply. No Meta key, no network.

Oracle (HANDOFF-AI-RESCHEDULE 2026-11-04): now 14:00, rest 180 min → 14:00–17:00, day end 21:00.
"""
import json,subprocess,sys,tempfile,unittest
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError
from store import Store,DomainError
import rest_demo
from rest_reschedule import meta_context,suggestions

HERE=Path(__file__).resolve().parent

class RestMinutesStore(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.s=Store(Path(self.tmp.name)/'db')
    def tearDown(self):self.tmp.cleanup()
    def save(self,key,content,**kw):return self.s.command(dict(commandId=key,kind='saveDefinition',content=content,**kw))['routine']
    def test_optional_and_backward_compatible(self):
        steps=[{'id':'a','title':'Rest'}]
        old=self.save('old',{'title':'No rest','steps':steps});self.assertNotIn('restMinutes',old)
        rest=self.save('rest',{'title':'Burnout reset','steps':steps,'restMinutes':180});self.assertEqual(rest['restMinutes'],180)
        cleared=self.save('clear',{'title':'Burnout reset','steps':steps,'restMinutes':None},definitionId=rest['id'],expectedVersion=1)
        self.assertNotIn('restMinutes',cleared);self.assertEqual(self.s.version(rest['id'],1)['restMinutes'],180)
        for bad in (0,721,'180',True,1.5):
            with self.assertRaises(DomainError):self.save('bad-'+repr(bad),{'title':'x','steps':steps,'restMinutes':bad})

class FakeMeta:
    """Stands in for MetaProvider.reschedule. Records every call so duplicate charges are visible."""
    calls=[];reply=None
    def __init__(self):self.language='en';self.metrics=[]
    def reschedule(self,context):
        FakeMeta.calls.append(context)
        if isinstance(FakeMeta.reply,Exception):raise FakeMeta.reply
        return FakeMeta.reply

class Fixture:
    """One disposable fixture + running services per test class (each start launches the KMP server)."""
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.data=Path(cls.tmp.name)/'fixture'
        cls.fixture=rest_demo.prepare(cls.data,'14:00')
        anchor=json.loads((cls.data/'demo-fixture.json').read_text())['nowMillis'];cls.day=datetime.fromtimestamp(anchor/1000).date()
        cls.ctx=rest_demo.services(cls.data,provider_factory=FakeMeta);cls.base=cls.ctx.__enter__()
        FakeMeta.calls=[];FakeMeta.reply=cls.ai_reply()
        cls.call('/api/execution/demo/clock',{'setMillis':cls.at('14:00')})
        cls.report=cls.call('/api/execution/context')['workspace']['runs'][0]
        cls.before=cls.call('/api/execution/reservations')
        w=cls.call('/api/execution/context')['workspace'];b=cls.fixture['burnout']
        rest_demo.command(cls.base,{'id':'start-rest','kind':'start','occurrenceId':'rest','expectedRevision':w['revision'],'definition':{'id':b['id'],'version':b['version'],'title':b['title'],'author':b['author']['name'],'steps':b['steps']}})
    @classmethod
    def tearDownClass(cls):cls.ctx.__exit__(None,None,None);cls.tmp.cleanup()
    @classmethod
    def ai_reply(cls):return None
    @classmethod
    def call(cls,path,body=None):return rest_demo.request(cls.base,path,body)
    @classmethod
    def at(cls,hhmm):return rest_demo.millis(cls.day,hhmm)
    def propose(self,**kw):return self.call('/api/rest/proposal',dict(occurrenceId='rest',restMinutes=180,**kw))
    def apply(self,key,proposal,decisions):
        return self.call('/api/execution/reschedule/apply',{'id':key,'occurrenceId':'rest','restMinutes':180,'expectedRevision':proposal['expectedRevision'],'decisions':decisions})
    def times(self):return {r['title']:(r['startMillis'],r['endMillis'],r.get('status')) for r in self.call('/api/execution/reservations')}
    def by_title(self,p):return {i['reservation']['title']:i for i in p['items']}

class MockAiProposal(Fixture,unittest.TestCase):
    @classmethod
    def ai_reply(cls):
        # Team sync: valid. Budget: ends 21:30 > day end. Deep work: overlaps Write report section. Doctor: keep.
        return {'items':[{'id':'team-sync','action':'move','newStart':'19:00','reason':'After your rest.'},
                         {'id':'budget-draft','action':'move','newStart':'20:30','reason':'Late slot.'},
                         {'id':'deep-work-block','action':'move','newStart':'17:00','reason':'Right after rest.'},
                         {'id':'doctor-call','action':'keep','reason':'Required.'},
                         {'id':'write-report-section','action':'move','newStart':'19:30','reason':'Not a target.'}]}
    def test_1_ai_proposal_validated(self):
        out=self.propose();p=out['proposal'];items=self.by_title(p)
        self.assertEqual((out['ai']['status'],p['source']),('ok','ai'))
        self.assertEqual((p['restStartMillis'],p['restEndMillis'],p['dayEndMillis']),(self.at('14:00'),self.at('17:00'),self.at('21:00')))
        self.assertEqual(list(items),['Team sync','Doctor call','Budget draft','Deep work block'])
        # Meta saw only window, day end and schedule facts.
        ctx=FakeMeta.calls[0];self.assertEqual((ctx['restStart'],ctx['restEnd'],ctx['dayEnd']),('14:00','17:00','21:00'))
        self.assertEqual({t['id']:t['required'] for t in ctx['targets']},{'team-sync':False,'doctor-call':True,'budget-draft':False,'deep-work-block':False})
        self.assertEqual([b['title'] for b in ctx['busy']],['Write report section'])
        # Valid AI suggestion is shown as is.
        self.assertEqual(items['Team sync']['aiIssues'],[]);self.assertEqual((items['Team sync']['proposed']['source'],items['Team sync']['proposed']['newStartMillis']),('ai',self.at('19:00')))
        self.assertEqual(items['Doctor call']['proposed']['action'],'keep');self.assertEqual(items['Doctor call']['allowed'],['keep'])
        # Past 21:00 and overlapping suggestions need a check and are not offered as possible times.
        self.assertEqual(items['Budget draft']['aiIssues'],['PAST_DAY_END'])
        self.assertEqual(items['Deep work block']['aiIssues'],['OVERLAP'])
        for t in ('Budget draft','Deep work block'):
            self.assertEqual(items[t]['proposed']['source'],'rule');self.assertNotEqual(items[t]['proposed'].get('newStartMillis'),items[t]['ai']['newStartMillis'])
        self.assertEqual((items['Budget draft']['proposed']['action'],items['Budget draft']['proposed']['newStartMillis']),('move',self.at('19:30')))
        self.assertEqual(items['Deep work block']['proposed']['action'],'skip_this_time')
        self.assertEqual(out['rejected'],[{'reservationId':'write-report-section','code':'NOT_AFFECTED'}])
        # Preview changes nothing; reopening reuses the result (no second Meta charge).
        self.assertEqual(self.call('/api/execution/reservations'),self.before)
        self.assertEqual(self.propose(),out);self.assertEqual(len(FakeMeta.calls),1)
    def test_2_apply_all_defaults_then_twice(self):
        p=self.propose()['proposal'];decisions=[i['proposed'] for i in p['items']]
        first=self.apply('apply-1',p,decisions);self.assertEqual((first['accepted'],first['reason']),(True,'APPLIED'))
        self.assertEqual(self.times(),{'Team sync':(self.at('19:00'),self.at('19:30'),None),'Doctor call':(self.at('15:00'),self.at('15:15'),None),
            'Budget draft':(self.at('19:30'),self.at('20:30'),None),'Deep work block':(self.at('16:00'),self.at('18:00'),'skipped'),
            'Write report section':(self.at('17:30'),self.at('18:30'),None)})
        # Original time kept as history; skipped item still exists (no external cancellation).
        team=next(r for r in first['reservations'] if r['id']=='team-sync')
        self.assertEqual([(h['fromStartMillis'],h['action'],h['source']) for h in team['history']],[(self.at('14:30'),'move','ai')])
        self.assertEqual(self.apply('apply-1',p,decisions),first)
        again=self.apply('apply-2',p,decisions);self.assertEqual((again['accepted'],again['reason'],again['reservations']),(True,'ALREADY_APPLIED',first['reservations']))
        self.assertEqual(self.apply('apply-1',p,decisions[1:])['reason'],'COMMAND_CONFLICT')
        # The in-progress report run keeps its exact step.
        runs={r['id']:r for r in self.call('/api/execution/context')['workspace']['runs']}
        self.assertEqual(runs['demo-report'],self.report);self.assertEqual(runs['demo-report']['currentUnitId'],'heading')

class RuleFallbackAndOverride(Fixture,unittest.TestCase):
    @classmethod
    def ai_reply(cls):return TimeoutError('slow')  # unexpected exception type: still labelled, no crash
    def test_1_meta_timeout_shows_rule_plan(self):
        from store import DomainError as E
        FakeMeta.reply=E('META_TIMEOUT','late',504)
        out=self.propose(language='ko');p=out['proposal'];items=self.by_title(p)
        self.assertEqual((out['ai'],p['source']),({'status':'error','code':'META_TIMEOUT'},'rule'))
        self.assertEqual(len(FakeMeta.calls),1)
        # Rule-based alternative oracle.
        self.assertEqual((items['Team sync']['proposed']['action'],items['Team sync']['proposed']['newStartMillis']),('move',self.at('17:00')))
        self.assertEqual((items['Budget draft']['proposed']['action'],items['Budget draft']['proposed']['newStartMillis']),('move',self.at('18:30')))
        self.assertEqual(items['Deep work block']['proposed']['action'],'skip_this_time')
        self.assertEqual(items['Doctor call']['proposed']['action'],'keep');self.assertNotIn('Write report section',items)
        self.assertEqual(self.propose(language='ko'),out);self.assertEqual(len(FakeMeta.calls),1)  # no automatic retry
        FakeMeta.reply=E('META_TIMEOUT','late',504)
        self.propose(language='ko',retryAi=True);self.assertEqual(len(FakeMeta.calls),2)
        FakeMeta.reply=TimeoutError('slow');unexpected=self.propose();self.assertEqual(unexpected['ai'],{'status':'error','code':'META_UNAVAILABLE'})  # en key: TimeoutError reply
        self.assertEqual(len(FakeMeta.calls),3)  # explicit user retry only
    def test_2_invalid_choice_refused_then_keep_one(self):
        p=self.propose()['proposal'];defaults=[i['proposed'] for i in p['items']]
        def swap(id,d):return [d if x['reservationId']==id else x for x in defaults]
        bad=self.apply('bad',p,swap('team-sync',{'reservationId':'team-sync','action':'move','newStartMillis':self.at('20:45'),'source':'user'}))
        self.assertEqual((bad['accepted'],bad['reason'],bad['issues']),(False,'INVALID_DECISIONS',[{'reservationId':'team-sync','code':'PAST_DAY_END'}]))
        dry=self.call('/api/execution/reschedule/apply',{'id':'dry','dryRun':True,'occurrenceId':'rest','restMinutes':180,'expectedRevision':p['expectedRevision'],'decisions':swap('team-sync',{'reservationId':'team-sync','action':'keep','source':'user'})})
        self.assertEqual(dry['reason'],'VALID');self.assertEqual(self.call('/api/execution/reservations'),self.before)
        out=self.apply('keep-one',p,swap('team-sync',{'reservationId':'team-sync','action':'keep','source':'user'}))
        self.assertEqual(out['reason'],'APPLIED')
        t=self.times()
        self.assertEqual(t['Team sync'],(self.at('14:30'),self.at('15:00'),None))
        self.assertEqual(t['Budget draft'],(self.at('18:30'),self.at('19:30'),None));self.assertEqual(t['Deep work block'][2],'skipped')
        stale=self.apply('stale',p,defaults);self.assertEqual(stale['reason'],'STALE_REVISION')

class LaterAndTimeSkip(Fixture,unittest.TestCase):
    def test_later_and_three_hours_later(self):
        out=self.propose();p=out['proposal'];self.assertEqual(out['ai'],{'status':'error','code':'META_INVALID'})
        decisions=[{'reservationId':'deep-work-block','action':'later','source':'user'} if i['reservation']['id']=='deep-work-block' else i['proposed'] for i in p['items']]
        self.assertEqual(self.apply('a',p,decisions)['reason'],'APPLIED')
        deep=next(r for r in self.call('/api/execution/reservations') if r['id']=='deep-work-block')
        self.assertEqual((deep['status'],deep['startMillis']),('unscheduled',self.at('16:00')))  # no invented time
        # Three hours later (demo clock): after finishing the rest steps the next reservation is the moved Team sync.
        self.call('/api/execution/demo/clock',{'advanceMinutes':180})
        rest_run=next(r for r in self.call('/api/execution/context')['workspace']['runs'] if r['id']=='rest')
        for _ in rest_run['steps']:
            w=self.call('/api/execution/context')['workspace'];r=next(x for x in w['runs'] if x['id']==w['focusId'])
            rest_demo.command(self.base,{'id':'done-'+r['currentUnitId'],'kind':'complete','occurrenceId':r['id'],'expectedRevision':r['revision'],'unitId':r['currentUnitId'],'expectedFocusRevision':w['focusRevision']})
        nxt=self.call('/api/execution/context')['reservation']
        self.assertEqual((nxt['state'],nxt['candidates'][0]['title'],nxt['candidates'][0]['startMillis']),('selected','Team sync',self.at('17:00')))
        report=next(r for r in self.call('/api/execution/context')['workspace']['runs'] if r['id']=='demo-report')
        self.assertEqual(report['currentUnitId'],'heading')
    @classmethod
    def ai_reply(cls):return 'not an object'

class Shapes(unittest.TestCase):
    proposal={'restStartMillis':0,'restEndMillis':1,'dayEndMillis':2,'items':[],'fixed':[]}
    def test_suggestion_shape_is_lenient_but_never_invents_a_valid_time(self):
        out=suggestions({'items':[{'id':'a','action':'move','newStart':'25:99','reason':'x'},{'id':'b','action':'cancel','newStart':'','reason':'x'},{'bad':1}]},self.proposal)
        self.assertEqual([(x['reservationId'],x['action'],x['newStartMillis']) for x in out],[('a','move',None),('b','invalid',None)])
        with self.assertRaises(DomainError):suggestions('x',self.proposal)

class ProviderRequest(unittest.TestCase):
    def test_reschedule_request_uses_schedule_prompt_and_strict_schema(self):
        from meta_provider import MetaProvider,MODEL
        from test_meta_integration import Opener,response
        o=Opener(response({'items':[{'id':'a','action':'keep','newStart':'','reason':'ok'}]}));p=MetaProvider('synthetic-key',o)
        ctx={'restStart':'14:00','restEnd':'17:00','dayEnd':'21:00','targets':[{'id':'a','title':'Team sync','start':'14:30','end':'15:00','minutes':30,'required':False,'movable':True,'deadline':''}],'busy':[]}
        self.assertEqual(p.reschedule(ctx)['items'][0]['action'],'keep')
        req,timeout=o.requests[0];body=json.loads(req.data)
        self.assertEqual((body['model'],body['response_format']['json_schema']['name'],body['response_format']['json_schema']['strict']),(MODEL,'reschedule',True))
        self.assertIn('휴식 모드',body['messages'][0]['content']);self.assertEqual(json.loads(body['messages'][1]['content']),ctx)
        self.assertNotIn('synthetic-key',req.data.decode());self.assertEqual(len(o.requests),1)

class DemoClockGuards(unittest.TestCase):
    def test_normal_mode_refuses_clock(self):
        with tempfile.TemporaryDirectory() as tmp:
            with rest_demo.services(Path(tmp),demo=False) as base:
                with self.assertRaises(HTTPError) as e:rest_demo.request(base,'/api/execution/demo/clock',{'advanceMinutes':180})
                self.assertEqual(e.exception.code,400)
    def test_run_integrated_refuses_non_fixture_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=subprocess.run([sys.executable,str(HERE/'run_integrated.py'),'--data',tmp,'--demo-clock'],capture_output=True,text=True,timeout=30)
            self.assertEqual(out.returncode,2);self.assertIn('disposable',out.stderr)
    def test_prepare_refuses_existing_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileExistsError):rest_demo.prepare(tmp)

if __name__=='__main__':unittest.main()
