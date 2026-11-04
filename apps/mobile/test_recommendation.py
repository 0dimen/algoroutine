"""Synthetic provider fixtures verify routing/structure, NOT AI quality."""
import unittest
from copy import deepcopy
from recommendation import select
from store import DomainError

CANDIDATE = {'id':'mine-1','version':2,'source':'mine','title':'나의 원문 제목',
             'author':{'name':'나'},'steps':[{'id':'one','title':'문서 열기'}]}
DRAFT = {'title':'문서 첫 문장 쓰기','description':'작게 시작하기',
         'steps':[{'id':'one','title':'새 문서 열기'}]}
CHOICE = {'id':'mine-1','version':2,'reason':'요청한 문서 시작에 맞아요.'}

class Fake:
    def __init__(self, response=None, generated=None):
        self.response = response if response is not None else {'status':'matched','choices':[CHOICE]}
        self.generated = generated if generated is not None else DRAFT
        self.calls = []
    def recommend(self, query, candidates):
        self.calls.append('recommend')
        candidates.clear()  # provider must not mutate caller snapshot
        if isinstance(self.response, Exception): raise self.response
        return deepcopy(self.response)
    def generate(self, query):
        self.calls.append('generate')
        return deepcopy(self.generated)

class RecommendationTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = {'items':[deepcopy(CANDIDATE)],'complete':True,
                         'filtered':False,'libraryRevision':7}
    def test_original_content_and_snapshot_preserved(self):
        before=deepcopy(self.snapshot);p=Fake()
        result=select('문서 시작',self.snapshot,p)
        self.assertEqual(result['items'][0]['routine'],CANDIDATE)
        result['items'][0]['routine']['title']='변경'
        self.assertEqual(self.snapshot,before)
        self.assertEqual(p.calls,['recommend'])
        self.assertEqual(result['libraryRevision'],7)
    def test_generation_only_after_valid_no_fit(self):
        p=Fake({'status':'no_fit','choices':[]})
        result=select('문서 시작',self.snapshot,p)
        self.assertEqual(p.calls,['recommend','generate'])
        self.assertEqual(result['content'],DRAFT)
        self.assertFalse(result['executable'])
        self.assertTrue(result['semanticReviewRequired'])
    def test_empty_snapshot_still_requires_provider_no_fit(self):
        self.snapshot['items']=[];p=Fake({'status':'no_fit','choices':[]})
        select('문서 시작',self.snapshot,p)
        self.assertEqual(p.calls,['recommend','generate'])
    def test_incomplete_filtered_and_missing_snapshot_rejected(self):
        for patch in ({'complete':False},{'filtered':True},{'libraryRevision':True}, {'items':None}):
            p=Fake()
            with self.assertRaises(DomainError):select('문서',dict(self.snapshot,**patch),p)
            self.assertEqual(p.calls,[])
    def test_error_is_not_no_fit(self):
        p=Fake(TimeoutError())
        with self.assertRaises(TimeoutError):select('문서',self.snapshot,p)
        self.assertEqual(p.calls,['recommend'])
    def test_bad_responses_never_generate(self):
        bad=[{}, {'status':'matched','choices':[]}, {'status':'error','choices':[]},
             {'status':'no_fit','choices':[CHOICE]}, {'status':'matched','choices':[CHOICE,CHOICE]},
             {'status':'matched','choices':[dict(CHOICE,id='invented')]},
             {'status':'matched','choices':[dict(CHOICE,version=1)]},
             {'status':'matched','choices':[dict(CHOICE,title='대체 제목')]},
             {'status':'matched','choices':[dict(CHOICE,reason=' ')]},
             {'status':'matched','choices':[dict(CHOICE,id=[])]}]
        for response in bad:
            with self.subTest(response=response):
                p=Fake(response)
                with self.assertRaises(DomainError):select('문서',self.snapshot,p)
                self.assertEqual(p.calls,['recommend'])
    def test_generation_structure_validation(self):
        for content in ({},dict(DRAFT,steps=[]),dict(DRAFT,author='나'),
                        dict(DRAFT,steps=[{'id':'1','title':'a'},{'id':'1','title':'b'}]),
                        dict(DRAFT,steps=[{'id':'1','title':'a','children':[]}])):
            p=Fake({'status':'no_fit','choices':[]},content)
            with self.assertRaises(DomainError) as e:select('문서',self.snapshot,p)
            self.assertEqual(e.exception.code,'GENERATION_INVALID')
            self.assertEqual(p.calls,['recommend','generate'])
    def test_source_priority_within_selected_matches(self):
        lib=dict(CANDIDATE,id='service',source='library')
        self.snapshot['items'].append(lib)
        p=Fake({'status':'matched','choices':[dict(CHOICE,id='service'),CHOICE]})
        result=select('문서',self.snapshot,p)
        self.assertEqual([x['routine']['id'] for x in result['items']],['mine-1','service'])
    def test_invalid_query_calls_nothing(self):
        for q in ('',' ','x'*501,None):
            p=Fake()
            with self.assertRaises(DomainError):select(q,self.snapshot,p)
            self.assertEqual(p.calls,[])

if __name__=='__main__':unittest.main()
