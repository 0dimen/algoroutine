import concurrent.futures
import json
import tempfile
import unittest
from pathlib import Path
from store import Store, DomainError

class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'data.sqlite3';self.s=Store(self.path)
        self.content={'title':' 내 제목 그대로 ','description':'설명','steps':[{'id':'a','title':'문서 열기'},{'id':'b','title':'한 줄 쓰기'}]}
    def tearDown(self):self.tmp.cleanup()
    def save(self,key='one',**kw):return self.s.command(dict(commandId=key,kind='saveDefinition',content=self.content,**kw))
    def test_library_rows_and_revision_share_one_snapshot(self):
        import sqlite3
        from unittest.mock import patch
        connect=sqlite3.connect
        with self.s.connect() as db:db.execute('PRAGMA journal_mode=WAL')
        writer=Store(self.path)
        fired=[]
        def traced(*args,**kwargs):
            db=connect(*args,**kwargs)
            def interleave(sql):
                if sql.startswith('SELECT value FROM metadata') and not fired:
                    fired.append(True)
                    writer.command({'commandId':'interleaved','kind':'saveDefinition','content':self.content})
            db.set_trace_callback(interleave)
            return db
        with patch('store.sqlite3.connect',traced):snapshot=self.s.library()
        self.assertEqual(fired,[True])
        self.assertEqual(snapshot,{'items':[],'revision':0})
        self.assertEqual(self.s.library()['revision'],1)

    def test_database_connection_closes_after_commit_and_rollback(self):
        import sqlite3
        with self.s.connect() as committed:committed.execute('SELECT 1')
        with self.assertRaises(sqlite3.ProgrammingError):committed.execute('SELECT 1')
        with self.assertRaises(ValueError):
            with self.s.connect() as rolled_back:
                rolled_back.execute("UPDATE metadata SET value=999")
                raise ValueError('synthetic rollback')
        with self.assertRaises(sqlite3.ProgrammingError):rolled_back.execute('SELECT 1')
        self.assertEqual(self.s.library()['revision'],0)

    def test_restart_preserves_exact_title_steps_and_author(self):
        result=self.save();reopened=Store(self.path).library();self.assertEqual(reopened['items'][0],result['routine']);self.assertEqual(reopened['items'][0]['title'],' 내 제목 그대로 ');self.assertEqual(reopened['revision'],1)
    def test_immutable_version_survives_edit(self):
        old=self.save()['routine'];self.content['title']='수정 제목';new=self.save('edit',definitionId=old['id'],expectedVersion=1)['routine'];self.assertEqual(new['version'],2);self.assertEqual(self.s.version(old['id'],1),old);self.assertEqual(new['steps'],old['steps'])
    def test_conflict_rolls_back_without_revision_change(self):
        old=self.save()['routine'];self.save('edit',definitionId=old['id'],expectedVersion=1)
        with self.assertRaises(DomainError) as e:self.save('stale',definitionId=old['id'],expectedVersion=1)
        self.assertEqual(e.exception.code,'VERSION_CONFLICT');self.assertEqual(self.s.library()['revision'],2)
    def test_idempotent_save_and_lookup(self):
        a=self.save();self.assertEqual(a,self.save());self.assertEqual(a,self.s.command_result('one'));self.assertEqual(len(self.s.library()['items']),1)
    def test_idempotency_payload_conflict(self):
        self.save();self.content['title']='다른 내용'
        with self.assertRaises(DomainError) as e:self.save()
        self.assertEqual(e.exception.code,'IDEMPOTENCY_CONFLICT');self.assertEqual(self.s.library()['revision'],1)
    def test_concurrent_duplicate_creates_one(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:results=list(pool.map(lambda _:self.save(),range(5)))
        self.assertTrue(all(x==results[0] for x in results));self.assertEqual(len(self.s.library()['items']),1)
    def test_draft_incomplete_survives_and_is_not_library(self):
        self.s.save_draft('new',0,{'title':'','steps':[]});self.assertEqual(Store(self.path).draft('new')['content']['title'],'');self.assertEqual(self.s.library()['items'],[])
    def test_newer_draft_is_not_overwritten(self):
        self.s.save_draft('new',0,{'title':'古'});self.s.save_draft('new',1,{'title':'새 초안'})
        with self.assertRaises(DomainError):self.s.save_draft('new',1,{})
        self.assertEqual(self.s.draft('new')['content']['title'],'새 초안')
    def test_collect_duplicate_preserves_author_and_origin(self):
        cmd={'commandId':'copy','kind':'collectRoutine','sourceId':'report-start','sourceVersion':1};r=self.s.command(cmd)['routine'];cmd['commandId']='copy-again';self.assertEqual(self.s.command(cmd)['routine']['id'],r['id']);self.assertEqual(r['author']['name'],'루틴 스튜디오');self.assertEqual(r['origin']['id'],'report-start');self.assertEqual(self.s.library()['revision'],1)
    def test_copy_edit_retains_attribution(self):
        r=self.s.command({'commandId':'copy','kind':'collectRoutine','sourceId':'report-start','sourceVersion':1})['routine'];new=self.save('edit',definitionId=r['id'],expectedVersion=1)['routine'];self.assertEqual(new['origin'],r['origin']);self.assertEqual(new['author'],r['author'])
    def test_reject_invalid_definition_without_writes(self):
        for invalid in [{'title':'','steps':[]},{'title':'a','steps':[{'id':'same','title':'a'},{'id':'same','title':'b'}]},{'title':'a','steps':[{'id':'a','title':''}]}]:
            with self.assertRaises(DomainError):self.s.command({'commandId':'invalid','kind':'saveDefinition','content':invalid})
        self.assertEqual(self.s.library()['revision'],0)
    def test_drafts_separated_by_target(self):
        self.s.save_draft('new',0,{'title':'신규'});self.s.save_draft('existing',0,{'title':'기존'});self.assertEqual(self.s.draft('new')['content']['title'],'신규')

if __name__=='__main__':unittest.main()
