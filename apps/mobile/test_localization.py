import json,re,unittest
from pathlib import Path
from localization import CATALOG,translate
from meta_provider import MetaProvider
from test_meta_integration import Opener,response
ROOT=Path(__file__).resolve().parents[2]
class LocalizationTests(unittest.TestCase):
 def test_catalog_keys_and_placeholders_match(self):
  en=CATALOG['en'];self.assertEqual(set(en),set(CATALOG['ko']))
  for lang,values in CATALOG.items():
   for key,text in values.items():
    self.assertTrue(text);self.assertEqual(set(re.findall(r'\{\w+\}',text)),set(re.findall(r'\{\w+\}',en[key])))
 def test_default_and_unknown_language_are_english(self):
  self.assertEqual(translate('완료'),'Done');self.assertEqual(translate('완료','unknown'),'Done');self.assertEqual(translate('완료','ko'),'완료')
 def test_model_language_and_existing_content(self):
  for language,expected in [('en','English'),('ko','Korean')]:
   o=Opener(response({'status':'no_fit','choices':[]}));p=MetaProvider('test-key',o,language=language)
   routine={'id':'x','version':1,'source':'mine','title':'내 제목 그대로','steps':[{'id':'s','title':'My original action'}]}
   p.recommend('request',[routine]);body=json.loads(o.requests[0][0].data)
   self.assertIn('in '+expected,body['messages'][0]['content'])
   self.assertEqual(json.loads(body['messages'][1]['content'])['candidates'][0]['title'],routine['title'])
 def test_timeout_phase_and_no_retry(self):
  from store import DomainError
  o=Opener(TimeoutError());p=MetaProvider('test-key',o)
  with self.assertRaises(DomainError):p.recommend('q',[])
  self.assertEqual(len(o.requests),1);self.assertEqual(p.metrics[0]['phase'],'awaiting_headers');self.assertEqual(p.metrics[0]['failure'],'timeout')
 def test_ui_msgids_are_in_catalog(self):
  files=[ROOT/'apps/mobile/web/app.js',ROOT/'apps/mobile/web/voice.js',ROOT/'apps/watch-proof/appleWatch/RoutineWatchApp.swift',* (ROOT/'apps/watch-proof/wearApp/src/main/java/app/algoroutine/wear').glob('*.kt')]
  for p in files:
   if p.name=='AppLanguage.kt':continue
   for key in re.findall(r'\b(?:t|tr|L)\([\'\"]([^\'\"\n]*)[\'\"]',p.read_text()):
    if re.search('[가-힣]',key):self.assertIn(key,CATALOG['en'],str(p))
