"""Opt-in, bounded synthetic live check. Never touches the user's library.
At most four model calls, sequential, no retries. Saves synthetic responses for
human review; structural pass is not a semantic-quality or latency SLA claim.
"""
import argparse,json,time
from pathlib import Path
from meta_provider import MetaProvider
from recommendation import select
from store import DomainError

class BudgetedProvider:
 def __init__(self,provider,budget):self.provider=provider;self.budget=budget
 @property
 def metrics(self):return self.provider.metrics
 def invoke(self,method,*args):
  if self.budget[0]<=0:raise DomainError('LIVE_CHECK_BUDGET','Synthetic check call budget exhausted',429)
  self.budget[0]-=1
  return getattr(self.provider,method)(*args)
 def recommend(self,*args):return self.invoke('recommend',*args)
 def generate(self,*args):return self.invoke('generate',*args)

def main():
 p=argparse.ArgumentParser();p.add_argument('--live',action='store_true');p.add_argument('--output',required=True);a=p.parse_args()
 if not a.live:p.error('--live explicitly authorizes up to four paid synthetic calls')
 routine={'id':'synthetic-report','version':1,'source':'mine','title':'내가 쓴 보고서 시작','description':'Start a report with a heading and three bullet points.','steps':[{'id':'open','title':'Open a blank document'},{'id':'heading','title':'Write the report heading'},{'id':'bullets','title':'Write three key points'}]}
 cases=[('match-en','en','I need to start a report. Find my saved report routine.',[routine],'matched'),('match-ko','ko','내가 만든 보고서 시작 루틴을 찾아줘.',[routine],'matched'),('generate-en','en','Before leaving home, I want to check whether my potted plants need water.',[],'generated_draft')]
 # The generation case costs two calls; total maximum is four for this suite.
 budget=[4];rows=[];out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
 for name,language,query,items,expected in cases:
  provider=MetaProvider.local();provider.language=language;provider=BudgetedProvider(provider,budget);start=time.monotonic()
  row={'case':name,'language':language,'input':query,'expectedStatus':expected}
  try:
   result=select(query,{'complete':True,'filtered':False,'libraryRevision':0,'items':items},provider)
   row.update(result=result,structuralPass=result['status']==expected)
   if result['status']=='matched':row['originalPreserved']=all(x['routine']==routine for x in result['items'])
  except DomainError as exc:row.update(errorCode=exc.code,structuralPass=False)
  row.update(elapsedMs=round((time.monotonic()-start)*1000),calls=provider.metrics);rows.append(row)
  out.write_text(json.dumps({'scope':'synthetic, no persistence or execution; no retry','cases':rows},ensure_ascii=False,indent=2)+'\n')
  print(name,row.get('errorCode',row.get('result',{}).get('status')),row['elapsedMs'],flush=True)
if __name__=='__main__':main()
