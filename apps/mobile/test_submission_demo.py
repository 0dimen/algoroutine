import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from prepare_submission_demo import prepare,SelectionOnlyProvider
from store import DomainError
class DemoSafety(unittest.TestCase):
 def test_existing_directory_is_not_reset(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'keep').write_text('existing')
   with self.assertRaises(FileExistsError):prepare(p)
   self.assertEqual((p/'keep').read_text(),'existing');self.assertEqual(len(list(p.iterdir())),1)
 def test_non_temporary_destination_rejected(self):
  with self.assertRaises(ValueError):prepare(Path.home()/'must-not-create-demo')
 def test_live_selection_one_call_only(self):
  p=SelectionOnlyProvider('synthetic-test-key')
  with patch('meta_provider.MetaProvider.recommend',return_value={'status':'matched','choices':[]}) as call:
   p.recommend('q',[])
   with self.assertRaises(DomainError):p.recommend('q',[])
   self.assertEqual(call.call_count,1)
 def test_no_fit_never_spends_generation_call(self):
  p=SelectionOnlyProvider('synthetic-test-key')
  with patch('meta_provider.MetaProvider.generate') as call:
   with self.assertRaises(DomainError):p.generate('q')
   call.assert_not_called()
if __name__=='__main__':unittest.main()
