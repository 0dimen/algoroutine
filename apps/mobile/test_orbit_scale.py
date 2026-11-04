"""Orbit time scale by depth (2026-11-04 user decision): My routine 2 h / 10 min ticks, routine 30 min / 5 min,
step 10 min / 1 min. Values live in the shared core (OrbitScales); the execution server sends them with the
wall-clock ticks for "now", so the phone only draws them. Disposable rest_demo fixture (demo clock 14:00)."""
import unittest
from test_rest_reschedule import Fixture

class OrbitScaleContext(Fixture,unittest.TestCase):
    def orbit(self):return self.call('/api/execution/context')['orbit']
    def test_1_depth_scales_come_from_the_core(self):
        o=self.orbit()
        self.assertEqual({d:(o[d]['scale']['windowMinutes'],o[d]['scale']['tickMinutes']) for d in o},{'day':(120,10),'routine':(30,5),'step':(10,1)})
    def test_2_ticks_are_on_real_clock_marks_and_slide_with_the_clock(self):
        # mid-minute so the running demo clock never sits on a tick boundary
        self.call('/api/execution/demo/clock',{'setMillis':self.at('14:00')+30000})
        day=self.orbit()['day']['ticks']
        self.assertEqual([t['atMillis'] for t in day],[self.at(h) for h in ['13:10','13:20','13:30','13:40','13:50','14:00','14:10','14:20','14:30','14:40','14:50','15:00']])
        self.assertEqual([t['atMillis'] for t in day if t['label']],[self.at('14:00'),self.at('15:00')])
        at=lambda ticks,v:next(t['offset'] for t in ticks if t['atMillis']==v)
        before=at(day,self.at('14:30'))
        self.call('/api/execution/demo/clock',{'advanceMinutes':1})
        after=at(self.orbit()['day']['ticks'],self.at('14:30'))
        self.assertAlmostEqual(before-after,1/60,places=3)  # (the demo clock keeps running a few ms)  one minute later the 14:30 tick is 1/60 of the half-window closer to now
        step=self.orbit()['step']['ticks']
        self.assertEqual([t['atMillis'] for t in step],[self.at('13:57')+i*60000 for i in range(10)]);self.assertTrue(all(-1<=t['offset']<=1 for t in step))

    def test_3_clock_slots_place_nodes_by_time_and_turn_every_minute(self):
        self.call('/api/execution/demo/clock',{'setMillis':self.at('14:00')+30000})
        ctx=self.call('/api/execution/context');focus=ctx['workspace']['focusId']
        rest=ctx['clock']['runs'][focus]  # Burnout reset, no time window -> default 5 min per step
        self.assertEqual([s['role'] for s in rest],['current','next','next']);self.assertEqual(rest[0]['offset'],0)
        self.assertEqual(rest[0]['endMillis']-rest[0]['startMillis'],5*60000);self.assertEqual([s['atMillis']-rest[1]['atMillis'] for s in rest[1:]],[0,5*60000])
        report=next(r for r in ctx['workspace']['runs'] if r['definition']['title']=='Start a report')
        run=ctx['clock']['runs'][report['id']]  # completed "Open a blank document", current "Write a working heading"
        self.assertEqual([s['role'] for s in run],['done','current','next'])
        cur=run[1];self.assertEqual(cur['offset'],0);self.assertGreater(cur['endMillis'],ctx['serverNow']);self.assertLessEqual(cur['startMillis'],ctx['serverNow'])
        self.assertEqual(run[2]['atMillis'],cur['endMillis'])  # next step starts at the current step's expected end
        day={s['id']:s for s in ctx['clock']['day']};self.assertEqual(day[focus]['role'],'current');self.assertEqual(day[focus]['offset'],0)
        self.call('/api/execution/demo/clock',{'advanceMinutes':1})
        later=self.call('/api/execution/context')['clock']
        self.assertAlmostEqual(run[0]['offset']-later['runs'][report['id']][0]['offset'],1/15,places=3)
        for x in ctx['clock']['day']:
            y=next(s for s in later['day'] if s['id']==x['id'])
            if x['role']=='item' and not x['hidden'] and not y['hidden']:self.assertAlmostEqual(x['offset']-y['offset'],1/60,places=3)

if __name__=='__main__':unittest.main()
