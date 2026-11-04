"""Add to My routine (2026-11-04 user decision): a plain schedule (no steps) or a routine, always with start–end.

Disposable rest_demo fixture (demo clock 14:00), mock Meta only. Plain schedule = reservation kind "schedule",
definitionId "schedule" v1, no routine definition; started at its time it is a zero-step run that Done completes.
"""
import unittest
from urllib.error import HTTPError
from test_rest_reschedule import Fixture,FakeMeta

def plain(key,title,start,end,**facts):
    return {'id':key,'kind':'schedule','definitionId':'schedule','definitionVersion':1,'title':title,'startMillis':start,'endMillis':end,
            'required':facts.get('required',False),'movable':facts.get('movable',True),'deadlineMillis':facts.get('deadline')}

class AddPlainSchedule(Fixture,unittest.TestCase):
    def day_items(self):return [(x['kind'],x['id'],x.get('plain',False)) for x in self.call('/api/execution/context')['day']]
    def test_1_add_schedule_appears_in_time_order_and_is_idempotent(self):
        body=plain('add-team-sync','  Team sync ',self.at('17:00'),self.at('17:30'))
        items=self.call('/api/execution/reservations',body)
        saved=next(r for r in items if r['id']=='add-team-sync')
        self.assertEqual((saved['kind'],saved['title'],saved['definitionId'],saved['definitionVersion'],saved['occurrenceId']),('schedule','Team sync','schedule',1,'reserved-add-team-sync'))
        self.assertEqual((saved['startMillis'],saved['endMillis'],saved['required'],saved['movable']),(self.at('17:00'),self.at('17:30'),False,True))
        # Same request again: no duplicate. Same id with different content: refused.
        self.assertEqual(self.call('/api/execution/reservations',body),items)
        with self.assertRaises(HTTPError) as e:self.call('/api/execution/reservations',{**body,'title':'Other'})
        self.assertEqual(e.exception.code,400)
        ids=[i for _,i,_ in self.day_items()]
        # Between Deep work block (16:00) and Write report section (17:30); the existing routine reservations stay routines.
        self.assertLess(ids.index('deep-work-block'),ids.index('add-team-sync'));self.assertLess(ids.index('add-team-sync'),ids.index('write-report-section'))
        self.assertIn(('reservation','add-team-sync',True),self.day_items());self.assertIn(('reservation','team-sync',False),self.day_items())
        self.assertEqual({r['id']:r.get('kind') for r in self.call('/api/execution/reservations')}['team-sync'],'routine')
    def test_2_end_not_after_start_is_not_saved(self):
        before=self.call('/api/execution/reservations')
        for start,end in [('18:00','18:00'),('18:30','18:00')]:
            with self.assertRaises(HTTPError) as e:self.call('/api/execution/reservations',plain('bad-'+start,'Bad',self.at(start),self.at(end)))
            self.assertEqual(e.exception.code,400)
        for bad in [{'title':'   '},{'kind':'other'},{'deadlineMillis':self.at('18:00')}]:
            with self.assertRaises(HTTPError):self.call('/api/execution/reservations',{**plain('bad-x','Ok',self.at('19:00'),self.at('19:30')),**bad})
        self.assertEqual(self.call('/api/execution/reservations'),before)
    def test_3_plain_schedule_never_starts_itself_then_start_and_done(self):
        d={'id':'schedule','version':1,'title':'x','author':'','steps':[]}
        def start(key):return self.call('/api/execution/command',{'id':key,'kind':'start','occurrenceId':'reserved-add-team-sync','expectedRevision':self.call('/api/execution/context')['workspace']['revision'],'definition':d})
        self.assertEqual(start('early-sync')['result']['reason'],'EARLY_START')
        self.call('/api/execution/demo/clock',{'setMillis':self.at('17:05')})
        c=self.call('/api/execution/context')
        self.assertNotIn('reserved-add-team-sync',[r['id'] for r in c['workspace']['runs']]);self.assertIn(('reservation','add-team-sync',True),self.day_items())
        # A plain schedule id cannot be started outside its reservation.
        with self.assertRaises(HTTPError):self.call('/api/execution/command',{'id':'free','kind':'start','occurrenceId':'free','expectedRevision':c['workspace']['revision'],'definition':d})
        out=start('start-sync');self.assertTrue(out['result']['accepted'])
        run=next(r for r in out['context']['workspace']['runs'] if r['id']=='reserved-add-team-sync')
        self.assertEqual((run['definition']['title'],run['definition']['steps'],run['currentUnitId'],run['status']),('Team sync',[],None,'running'))
        self.assertEqual((run['definition']['windowStartMillis'],run['definition']['windowEndMillis']),(self.at('17:00'),self.at('17:30')))
        self.assertEqual(out['context']['workspace']['focusId'],'reserved-add-team-sync')
        item=next(x for x in out['context']['day'] if x['id']=='reserved-add-team-sync');self.assertEqual((item['kind'],item['plain'],item['total']),('run',True,0))
        w=out['context']['workspace']
        done=self.call('/api/execution/command',{'id':'done-sync','kind':'completeParent','occurrenceId':run['id'],'expectedRevision':run['revision'],'unitId':None,'expectedFocusRevision':w['focusRevision']})
        self.assertTrue(done['result']['accepted'])
        run=next(r for r in done['context']['workspace']['runs'] if r['id']=='reserved-add-team-sync');self.assertEqual((run['status'],run['evidence']),('completed','direct_parent'))
        self.assertNotIn('reserved-add-team-sync',[x['id'] for x in done['context']['day']])
        # The other run keeps its step.
        self.assertEqual(next(r for r in done['context']['workspace']['runs'] if r['id']=='demo-report')['currentUnitId'],'heading')

class AddRoutineReservation(Fixture,unittest.TestCase):
    def test_routine_reservation_starts_its_steps_at_its_time(self):
        b=self.fixture['burnout']
        items=self.call('/api/execution/reservations',{'id':'add-burnout','kind':'routine','definitionId':b['id'],'definitionVersion':b['version'],'title':'ignored','startMillis':self.at('20:00'),'endMillis':self.at('21:00'),'required':False,'movable':True,'deadlineMillis':None})
        saved=next(r for r in items if r['id']=='add-burnout');self.assertEqual((saved['kind'],saved['title']),('routine','Burnout reset'))
        self.assertIn('add-burnout',[x['id'] for x in self.call('/api/execution/context')['day'] if not x.get('plain')])
        self.call('/api/execution/demo/clock',{'setMillis':self.at('20:00')})
        w=self.call('/api/execution/context')['workspace']
        out=self.call('/api/execution/command',{'id':'start-burnout','kind':'start','occurrenceId':'reserved-add-burnout','expectedRevision':w['revision'],'definition':{'id':b['id'],'version':b['version'],'title':b['title'],'author':'','steps':[]}})
        self.assertTrue(out['result']['accepted'])
        run=next(r for r in out['context']['workspace']['runs'] if r['id']=='reserved-add-burnout')
        self.assertEqual(([s['id'] for s in run['steps']],run['currentUnitId']),(['phone','water','rest'],'phone'))

class PlainScheduleInRest(Fixture,unittest.TestCase):
    """Rest 14:00–17:00 (started in the fixture). Plain schedules inside it go through the same AI + rule proposal."""
    @classmethod
    def ai_reply(cls):
        return {'items':[{'id':'call-mom','action':'move','newStart':'19:00','reason':'Evening.'},
                         {'id':'standup','action':'move','newStart':'19:30','reason':'Try later.'}]}
    def test_plain_schedules_are_proposed_and_rules_hold(self):
        self.call('/api/execution/reservations',plain('call-mom','Call mom',self.at('15:15'),self.at('15:30')))
        self.call('/api/execution/reservations',plain('standup','Standup',self.at('14:15'),self.at('14:30'),required=True))
        out=self.call('/api/rest/proposal',{'occurrenceId':'rest','restMinutes':180});p=out['proposal'];items={i['reservation']['id']:i for i in p['items']}
        self.assertEqual(out['ai']['status'],'ok');self.assertIn('call-mom',items);self.assertIn('standup',items)
        targets={t['id']:t for t in FakeMeta.calls[-1]['targets']};self.assertEqual((targets['call-mom']['title'],targets['standup']['required']),('Call mom',True))
        self.assertEqual((items['call-mom']['proposed']['action'],items['call-mom']['proposed']['newStartMillis'],items['call-mom']['proposed']['source']),('move',self.at('19:00'),'ai'))
        self.assertEqual(items['standup']['aiIssues'],['REQUIRED_FIXED']);self.assertEqual(items['standup']['proposed']['action'],'keep');self.assertEqual(items['standup']['allowed'],['keep'])
        res=self.call('/api/execution/reschedule/apply',{'id':'apply-plain','occurrenceId':'rest','restMinutes':180,'expectedRevision':p['expectedRevision'],'decisions':[i['proposed'] for i in p['items']]})
        self.assertEqual(res['reason'],'APPLIED');after={r['id']:r for r in res['reservations']}
        self.assertEqual((after['call-mom']['startMillis'],after['call-mom']['endMillis'],after['call-mom']['kind']),(self.at('19:00'),self.at('19:15'),'schedule'))
        self.assertEqual(after['standup']['startMillis'],self.at('14:15'))

if __name__=='__main__':unittest.main()
