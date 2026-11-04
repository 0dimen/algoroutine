"""Deterministic local lexical retrieval. No inference, query persistence or remote AI calls."""
import re,unicodedata
from store import CATALOG,DomainError

def normalize(value):return unicodedata.normalize('NFKC',value).casefold().strip()

def search(store,query):
    if not isinstance(query,str) or len(query)>500:
        raise DomainError('INVALID_QUERY','찾을 내용을 500자 이내로 입력해 주세요.')
    query=normalize(query)
    words=[w for w in re.findall(r'[\w]+',query) if (len(w)>1 or re.fullmatch('[가-힣]',w)) and w not in {'좀','더','나','내','것','수','하고','싶어','싶어요','너무','정말','어떻게','찾아줘'}]
    snapshot=candidate_snapshot(store)
    library={'revision':snapshot['libraryRevision']}
    candidates=snapshot['items']
    ranked=[]
    for index,r in enumerate(candidates):
        text=normalize(' '.join([r['title'],r.get('description','')]+[s['title'] for s in r['steps']]))
        hits=sum(w in text for w in words)
        if query and not hits:continue
        source={'mine':0,'collected':1,'library':2}.get(r['source'],2)
        score=hits+(3 if query and query in normalize(r['title']) else 0)
        ranked.append(((source,-score,index),r))
    return {'items':[r for _,r in sorted(ranked,key=lambda x:x[0])], 'libraryRevision':library['revision'],'mode':'lexical'}


def candidate_snapshot(store):
    """Complete local scope; lexical misses are not semantic no-fit."""
    library=store.library()
    origins={(r['origin']['id'],r['origin']['version']) for r in library['items'] if r.get('origin')}
    candidates=library['items']+[r for r in CATALOG if (r['id'],r['version']) not in origins]
    return {"items":candidates,"libraryRevision":library["revision"],"complete":True,"filtered":False}
