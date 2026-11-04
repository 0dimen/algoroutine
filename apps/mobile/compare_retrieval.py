"""Bounded opt-in comparison. Freeze/hash cases before calling the model.
Selection only, at most ten paid calls, no generation, retries, or user DB writes.
"""
import argparse,copy,hashlib,json,time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from meta_provider import MetaProvider
from store import DomainError
from search import search

def validate(response,candidates):
 known={r['id']:r for r in candidates}
 if not isinstance(response,dict) or set(response)!={'status','choices'}:raise ValueError('shape')
 choices=response['choices'];status=response['status']
 if not isinstance(choices,list) or status not in ['matched','no_fit']:raise ValueError('shape')
 if status=='no_fit':
  if choices:raise ValueError('no-fit with choices')
  return []
 if not 1<=len(choices)<=3:raise ValueError('count')
 seen=set()
 for c in choices:
  if not isinstance(c,dict) or set(c)!={'id','version','reason'}:raise ValueError('choice')
  if c['id'] not in known or c['id'] in seen or type(c['version']) is not int or c['version']!=known[c['id']]['version']:raise ValueError('identity')
  if not isinstance(c['reason'],str) or not c['reason'].strip() or len(c['reason'])>500:raise ValueError('reason')
  seen.add(c['id'])
 return [c['id'] for c in sorted(choices,key=lambda c:{'mine':0,'collected':1,'library':2}[known[c['id']]['source']])]

def score(ids,acceptable,error=None):
 if acceptable is None:return None
 if error:return {'top1':False,'top3':False}
 if not acceptable:return {'top1':not ids,'top3':not ids}
 return {'top1':bool(ids and ids[0] in acceptable),'top3':bool(set(ids[:3])&set(acceptable))}

def main():
 p=argparse.ArgumentParser();p.add_argument('--live',action='store_true');p.add_argument('--cases',default=str(Path(__file__).parent/'evaluation/search_cases.json'));p.add_argument('--output',required=True);a=p.parse_args()
 if not a.live:p.error('--live authorizes at most ten paid calls')
 raw=Path(a.cases).read_bytes();spec=json.loads(raw);assert len(spec['cases'])<=10
 out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
 report={'caseSha256':hashlib.sha256(raw).hexdigest(),'scope':spec['scope'],'cases':[]}
 # Both systems receive exactly the same complete candidate set. Lexical uses
 # the unchanged production ranking function; hide only the real app catalog.
 store=SimpleNamespace(library=lambda:{'revision':0,'items':copy.deepcopy(spec['candidates'])})
 for case in spec['cases']:
  start=time.monotonic()
  with patch('search.CATALOG',[]):lex=search(store,case['query'])
  ids=[r['id'] for r in lex['items'][:3]]
  row={'id':case['id'],'language':case['language'],'query':case['query'],'acceptable':case['acceptable'],'rationale':case['rationale'],'lexical':{'ids':ids,'elapsedMs':round((time.monotonic()-start)*1000,2),'score':score(ids,case['acceptable'])}}
  provider=MetaProvider.local();provider.language=case['language'];start=time.monotonic()
  try:
   response=provider.recommend(case['query'],copy.deepcopy(spec['candidates']));ids=validate(response,spec['candidates'])
   row['meta']={'ids':ids,'response':response,'score':score(ids,case['acceptable'])}
  except (DomainError,ValueError) as exc:
   code=exc.code if isinstance(exc,DomainError) else 'INVALID_RANKING'
   row['meta']={'ids':[],'errorCode':code,'score':score([],case['acceptable'],code)}
  row['meta'].update(elapsedMs=round((time.monotonic()-start)*1000),calls=provider.metrics)
  report['cases'].append(row);out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
  print(case['id'],row['lexical']['ids'],row['meta']['ids'],row['meta'].get('errorCode','ok'),flush=True)
if __name__=='__main__':main()
