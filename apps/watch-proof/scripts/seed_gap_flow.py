"""Fresh isolated local server only: two overlapping reservations and a short-run definition.
Uses ordinary APIs; never resets or edits user records.
"""
import json,time,uuid
from urllib.request import Request,urlopen

def call(path,body=None):
 req=Request('http://127.0.0.1:8780'+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json','X-Routine-App':'local'})
 with urlopen(req,timeout=10) as r:return json.load(r)
def create(title,description,steps):
 return call('/api/commands',{'commandId':str(uuid.uuid4()),'kind':'saveDefinition','content':{'title':title,'description':description,'steps':[{'id':str(i),'title':t} for i,t in enumerate(steps)]}})['routine']
a=create('예약 A','다음 예약 설명',['다음 행동'])
b=create('예약 B','처음 저장한 설명',['선택한 행동','다음 단계'])
c=create('짧은 예약','경과 확인',['잠깐 집중'])
now=int(time.time()*1000)
for key,r in [('gap-a',a),('gap-b',b)]:call('/api/execution/reservations',{'id':key,'definitionId':r['id'],'definitionVersion':1,'title':r['title'],'startMillis':now-1000,'endMillis':now+3600000})
print(json.dumps({'a':a,'b':b,'short':c},ensure_ascii=False))
