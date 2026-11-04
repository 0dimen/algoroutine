import tempfile,unittest
from pathlib import Path
from store import Store,DomainError,CATALOG
from search import search,candidate_snapshot
class SearchTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'db');self.counter=0
 def tearDown(self):self.tmp.cleanup()
 def save(self,title,steps):
  self.counter+=1
  return self.store.command({'commandId':str(self.counter),'kind':'saveDefinition','content':{'title':title,'steps':[{'id':str(i),'title':s} for i,s in enumerate(steps)]}})['routine']
 def test_priority_author_duplicates_and_drafts(self):
  mine=self.save('내 문서 시작',['문서 열기'])
  collected=self.store.command({'commandId':'collect','kind':'collectRoutine','sourceId':'report-start','sourceVersion':1})['routine']
  self.store.save_draft('draft',0,{'title':'문서 임시 초안'})
  before=self.store.library()
  result=search(self.store,'문서')
  self.assertEqual([r['id'] for r in result['items']],[mine['id'],collected['id']])
  self.assertEqual(result['items'][1]['author']['name'],'루틴 스튜디오')
  self.assertEqual(before,self.store.library())
 def test_no_match_not_irrelevant_fallback(self):
  self.save('보고서 시작',['문서 열기'])
  self.assertEqual(search(self.store,'우주선 정비')['items'],[])
  self.assertEqual(search(self.store,'너무 하고 싶어요')['items'],[])
 def test_catalog_and_latest_saved_version(self):
  self.assertEqual(search(self.store,'보고서')['items'][0]['id'],'report-start')
  r=self.save('산책',['밖으로 나가기'])
  self.store.command({'commandId':'edit','kind':'saveDefinition','definitionId':r['id'],'expectedVersion':1,'content':{'title':'차 한잔','steps':[{'id':'0','title':'물 끓이기'}]}})
  self.assertEqual(search(self.store,'산책')['items'],[])
  self.assertEqual(search(self.store,'물 끓이기')['items'][0]['version'],2)
 def test_korean_single_syllable_and_unicode(self):
  water=self.save('차 준비',['물 끓이기'])
  self.assertEqual(search(self.store,'물')['items'][0]['id'],water['id'])
  english=self.save('ABC planning',['write outline'])
  self.assertEqual(search(self.store,'ＡＢＣ')['items'][0]['id'],english['id'])
 def test_semantic_snapshot_is_unfiltered_and_keeps_saved_copy(self):
  mine=self.save('완전히 다른 제목',['물 마시기'])
  collected=self.store.command({'commandId':'collect-snapshot','kind':'collectRoutine','sourceId':'report-start','sourceVersion':1})['routine']
  self.store.save_draft('excluded',0,{'title':'초안'})
  self.assertEqual(search(self.store,'우주 정비')['items'],[])
  snapshot=candidate_snapshot(self.store)
  self.assertTrue(snapshot['complete']);self.assertFalse(snapshot['filtered'])
  self.assertEqual({x['id'] for x in snapshot['items']},{mine['id'],collected['id']}|{r['id'] for r in CATALOG if r['id']!='report-start'})
  self.assertEqual(snapshot['libraryRevision'],self.store.library()['revision'])
 def test_query_validation(self):
  for q in [None,[],1,'a'*501]:
   with self.assertRaises(DomainError):search(self.store,q)
  self.assertTrue(search(self.store,'')['items'])
if __name__=='__main__':unittest.main()
