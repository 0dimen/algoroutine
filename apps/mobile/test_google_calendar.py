"""Google Calendar import (read-only, secret iCal address or .ics text). Local fixtures only; never a real Google call.

Oracle: timed events of the server-clock day become plain schedules, Required (time cannot change), id "gcal-…" from the
event UID + occurrence; re-import never duplicates; all-day events are not added; rest reschedule keeps them.
"""
import calendar,json,os,stat,tempfile,unittest
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError
import google_calendar
from google_calendar import occurrences,fetch,GoogleCalendarImport
from store import DomainError
from test_rest_reschedule import Fixture

HERE=Path(__file__).resolve().parent
FIXTURE=(HERE/'fixtures/google-calendar.ics').read_text()
def utc(*a):return calendar.timegm(datetime(*a).timetuple())*1000

class Parse(unittest.TestCase):
    def setUp(self):self.items,self.counts=occurrences(FIXTURE,utc(2026,11,3),utc(2026,11,6))
    def by(self):return {(x['title'],x['startMillis']):x for x in self.items}
    def test_timezone_utc_recurring_and_overrides(self):
        got=[(x['title'],x['startMillis'],x['endMillis']) for x in self.items]
        self.assertEqual(sorted(got,key=lambda x:x[1]),[
            ('Walk',utc(2026,11,3,12),utc(2026,11,3,12,30)),  # Nov 4 is an EXDATE
            ('Standup call with a very long title that is folded by the export at seventy-five octets',utc(2026,11,4,1,30),utc(2026,11,4,2)),
            ('Rent',utc(2026,11,4,5),utc(2026,11,4,5,30)),  # monthly: first occurrence only
            ('Gym',utc(2026,11,4,11),utc(2026,11,4,12)),  # weekly Wednesday 20:00 Asia/Seoul
            ('Dentist, Dr. Kim',utc(2026,11,4,14),utc(2026,11,4,14,30)),  # 09:00 New York (EST after Nov 1)
            ('Walk (moved)',utc(2026,11,5,15),utc(2026,11,5,15,30))])
        self.assertEqual(self.counts,{'allDay':1,'unsupportedRepeat':1,'cancelled':1,'invalid':0})
        b=self.by();self.assertEqual(b[('Dentist, Dr. Kim',utc(2026,11,4,14))]['endMillis'],utc(2026,11,4,14,30))
        self.assertEqual(b[('Walk (moved)',utc(2026,11,5,15))]['endMillis'],utc(2026,11,5,15,30))
        self.assertTrue(all(x['id'].startswith('gcal-') and len(x['id'])==25 for x in self.items))
    def test_ids_stable_per_occurrence_and_override_keeps_original_key(self):
        again,_=occurrences(FIXTURE,utc(2026,11,3),utc(2026,11,6));self.assertEqual([x['id'] for x in again],[x['id'] for x in self.items])
        moved=next(x for x in self.items if x['title']=='Walk (moved)')
        self.assertEqual(moved['occurrence'],utc(2026,11,5,12)//1000)  # the original slot, so a moved instance updates in place
        self.assertEqual(len({x['id'] for x in self.items}),len(self.items))
    def test_window_and_count_until(self):
        items,_=occurrences(FIXTURE,utc(2026,11,10),utc(2026,11,12))
        self.assertEqual(sorted(x['title'] for x in items),['Gym','Walk'])  # Walk COUNT=10 ends Nov 10
        text=FIXTURE.replace('RRULE:FREQ=WEEKLY;BYDAY=WE','RRULE:FREQ=WEEKLY;BYDAY=WE;UNTIL=20261030T000000Z')
        self.assertNotIn('Gym',[x['title'] for x in occurrences(text,utc(2026,11,3),utc(2026,11,6))[0]])
    def test_malformed_lines_are_counted_not_fatal(self):
        items,counts=occurrences('BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:x\nDTSTART:nonsense\nEND:VEVENT\nBEGIN:VEVENT\nSUMMARY:no uid\nEND:VEVENT\nEND:VCALENDAR\n',0,utc(2030,1,1))
        self.assertEqual((items,counts['invalid']),([],2))

class Fetch(unittest.TestCase):
    def test_only_https_or_the_demo_file(self):
        for bad in ['http://example.com/basic.ics','file:///etc/passwd','ftp://x.y/z.ics','https://','x',None]:
            with self.assertRaises(DomainError) as e:fetch(bad)
            self.assertEqual(e.exception.code,'CALENDAR_URL')
        with self.assertRaises(DomainError):fetch('http://127.0.0.1:8795/demo/google.ics')  # not without --demo-ics
        with tempfile.NamedTemporaryFile('w',suffix='.ics',delete=False) as f:f.write('BEGIN:VCALENDAR\nEND:VCALENDAR\n')
        try:self.assertIn('VCALENDAR',fetch('http://127.0.0.1:8795/demo/google.ics',f.name))
        finally:os.unlink(f.name)
    def test_fetch_error_never_contains_the_address(self):
        secret='https://calendar.invalid/calendar/ical/me%40gmail.com/private-SECRET123/basic.ics'
        with self.assertRaises(DomainError) as e:fetch(secret)
        self.assertEqual(e.exception.code,'CALENDAR_FETCH');self.assertNotIn('SECRET123',e.exception.message)

def demo_ics(day,events):
    d=day.strftime('%Y%m%d');body=''.join(f'BEGIN:VEVENT\nUID:{uid}\nSUMMARY:{title}\n{start}\n{end}\n{extra}END:VEVENT\n'
        for uid,title,start,end,extra in [(u,t,s.replace('DAY',d),e.replace('DAY',d),x.replace('WD',day.strftime('%a')[:2].upper())) for u,t,s,e,x in events])
    return 'BEGIN:VCALENDAR\nVERSION:2.0\n'+body+'END:VCALENDAR\n'

EVENTS=[('dentist@g','Dentist','DTSTART;TZID=Asia/Seoul:DAYT153000','DTEND;TZID=Asia/Seoul:DAYT160000',''),
        ('dinner@g','Dinner with Mina','DTSTART;TZID=Asia/Seoul:DAYT210000','DTEND;TZID=Asia/Seoul:DAYT220000',''),
        ('morning@g','Morning swim','DTSTART;TZID=Asia/Seoul:DAYT070000','DTEND;TZID=Asia/Seoul:DAYT080000',''),
        ('allday@g','Holiday','DTSTART;VALUE=DATE:DAY','DTEND;VALUE=DATE:DAY',''),
        ('weekly@g','Piano lesson','DTSTART;TZID=Asia/Seoul:20261001T193000','DTEND;TZID=Asia/Seoul:20261001T200000','RRULE:FREQ=WEEKLY;BYDAY=WD\n')]

class ImportIntoMyRoutine(Fixture,unittest.TestCase):
    """Fixture day, server clock 14:00, rest 14:00–17:00 already running. The machine's zone is Asia/Seoul (the app's)."""
    def text(self,events=EVENTS):return demo_ics(self.day,events)
    def ours(self):return {r['id']:r for r in self.call('/api/execution/reservations') if r['id'].startswith('gcal-')}
    def test_1_import_required_fixed_and_idempotent(self):
        out=self.call('/api/calendar/google/import',{'ics':self.text()})
        self.assertEqual((out['added'],out['unchanged'],out['past'],out['allDay'],out['changed']),(3,0,1,1,0))
        got={r['title']:r for r in self.ours().values()}
        self.assertEqual(set(got),{'Dentist','Dinner with Mina','Piano lesson'})
        d=got['Dentist'];self.assertEqual((d['kind'],d['required'],d['movable'],d['startMillis'],d['endMillis'],d['deadlineMillis']),('schedule',True,False,self.at('15:30'),self.at('16:00'),None))
        self.assertEqual(got['Piano lesson']['startMillis'],self.at('19:30'))
        day={x['id'] for x in self.call('/api/execution/context')['day']};self.assertTrue(set(self.ours())<=day)
        # Re-import: nothing duplicated.
        again=self.call('/api/calendar/google/import',{'ics':self.text()})
        self.assertEqual((again['added'],again['unchanged']),(0,3));self.assertEqual(len(self.ours()),3)
        # The source mapping is kept locally; no address was given, so none is stored.
        saved=json.loads((self.data/'google-calendar.json').read_text())
        self.assertNotIn('url',saved);self.assertEqual({v['uid'] for v in saved['events'].values()},{'dentist@g','dinner@g','weekly@g'})
        self.assertEqual({v['source'] for v in saved['events'].values()},{'Google Calendar'})
        self.assertEqual(stat.S_IMODE((self.data/'google-calendar.json').stat().st_mode),0o600)
    def test_2_changed_in_google_is_reported_not_duplicated(self):
        moved=[(u,t,s.replace('T153000','T154500'),e,x) if u=='dentist@g' else (u,t,s,e,x) for u,t,s,e,x in EVENTS]
        before=self.ours();out=self.call('/api/calendar/google/import',{'ics':self.text(moved)})
        self.assertEqual((out['added'],out['changed'],out['unchanged']),(0,1,2));self.assertEqual(self.ours(),before)
    def test_3_rest_reschedule_keeps_imported_plans(self):
        p=self.propose()['proposal'];item=next(i for i in p['items'] if i['reservation']['title']=='Dentist')
        self.assertEqual((item['proposed']['action'],item['allowed']),('keep',['keep']))
    def test_4_saved_secret_address_reused_never_returned(self):
        secret='https://calendar.google.com/calendar/ical/me%40gmail.com/private-SECRET123/basic.ics'
        cal=GoogleCalendarImport(self.data/'secret-check',self.base+'/api/execution');(self.data/'secret-check').mkdir()
        seen=[];original=google_calendar.fetch
        google_calendar.fetch=lambda url,demo=None:(seen.append(url),self.text())[1]
        try:
            out=cal.run({'url':secret});self.assertNotIn('SECRET123',json.dumps(out))
            self.assertEqual(cal.status(),{'saved':True});out=cal.run({'url':''})
        finally:google_calendar.fetch=original
        self.assertEqual(seen,[secret,secret]);self.assertEqual(out['added'],0)
        self.assertEqual(stat.S_IMODE((self.data/'secret-check/google-calendar.json').stat().st_mode),0o600)
    def test_5_not_ical_is_refused(self):
        with self.assertRaises(HTTPError) as e:self.call('/api/calendar/google/import',{'ics':'<html>login</html>'})
        self.assertEqual(e.exception.code,422)

if __name__=='__main__':unittest.main()
