"""Serialize paid requests without blocking execution. Preview never starts work."""
import json
import os
import uuid
from datetime import datetime, timezone
import threading
import time
from recommendation import select
from search import candidate_snapshot
from store import DomainError
from localization import normalize

class RecommendationService:
    def __init__(self, store, provider_factory):
        self.store=store;self.provider_factory=provider_factory
        self.lock=threading.Lock()
        self.last_metrics=[]
        self.audit_error=False

    def recommend(self, query, language="en"):
        if not self.lock.acquire(blocking=False):
            raise DomainError('RECOMMENDATION_BUSY','추천을 준비하고 있어요. 잠시 후 다시 시도해 주세요.',409)
        try:
            provider=self.provider_factory();provider.language=normalize(language);started=time.monotonic()
            try:
                snapshot=candidate_snapshot(self.store)
                def ensure_current():
                    if self.store.library()['revision']!=snapshot['libraryRevision']:
                        raise DomainError('SEARCH_STALE','보관함이 변경됐어요. 다시 찾아 주세요.',409)
                result=select(query,snapshot,provider,ensure_current=ensure_current)
                if self.store.library()['revision']!=result['libraryRevision']:
                    raise DomainError('SEARCH_STALE','보관함이 변경됐어요. 다시 찾아 주세요.',409)
                if result['status']=='generated_draft':
                    proposal=self.store.propose_generated(result['content'])
                    items=[proposal]
                else:
                    items=[dict(x['routine'],recommendationReason=x['reason']) for x in result['items']]
                return {'items':items,'mode':'meta','libraryRevision':result['libraryRevision'],
                        'elapsedMs':round((time.monotonic()-started)*1000)}
            finally:
                self.last_metrics=list(getattr(provider,'metrics',[]))
                if self.last_metrics:
                    record={'requestId':str(uuid.uuid4()),'at':datetime.now(timezone.utc).isoformat(),'calls':self.last_metrics}
                    try:
                        fd=os.open(self.store.path+'.meta-usage.jsonl',os.O_WRONLY|os.O_APPEND|os.O_CREAT|os.O_NOFOLLOW,0o600)
                        with os.fdopen(fd,'a') as audit:
                            os.fchmod(audit.fileno(),0o600)
                            audit.write(json.dumps(record)+'\n')
                        self.audit_error=False
                    except OSError:
                        # Do not turn an acknowledged preview into a retry/second charge.
                        self.audit_error=True
        finally:self.lock.release()
