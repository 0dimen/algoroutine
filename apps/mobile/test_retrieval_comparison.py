import unittest
from compare_retrieval import score,validate
class ComparisonTest(unittest.TestCase):
 def test_no_fit_is_not_provider_failure(self):
  self.assertTrue(score([],[])['top1']);self.assertFalse(score([],[],'TIMEOUT')['top1'])
 def test_ambiguous_excluded(self):self.assertIsNone(score(['anything'],None))
 def test_identity_and_version(self):
  candidates=[{'id':'one','version':1,'source':'mine'}]
  for item in ({'id':'fake','version':1,'reason':'x'},{'id':'one','version':2,'reason':'x'}):
   with self.assertRaises(ValueError):validate({'status':'matched','choices':[item]},candidates)
 def test_duplicates_rejected(self):
  item={'id':'one','version':1,'reason':'x'}
  with self.assertRaises(ValueError):validate({'status':'matched','choices':[item,item]},[{'id':'one','version':1,'source':'mine'}])
 def test_source_priority_after_relevance(self):
  choices=[{'id':i,'version':1,'reason':'match'} for i in ('saved','own')]
  self.assertEqual(validate({'status':'matched','choices':choices},[{'id':'own','version':1,'source':'mine'},{'id':'saved','version':1,'source':'collected'}]),['own','saved'])
if __name__=='__main__':unittest.main()
