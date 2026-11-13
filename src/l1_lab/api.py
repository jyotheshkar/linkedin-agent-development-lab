"""Local REST exercise; optional bearer token, no outbound provider writes."""
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, ConfigDict, Field
from .contracts import Job
from .service import RAGService

app=FastAPI(title="L1 simulated fit API",version="0.2.0",docs_url=None,redoc_url=None)

class FitRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    job: Job
    query: str | None = Field(default=None,min_length=1,max_length=2000)

@app.get("/health")
def health(): return {"status":"ok","effects":"simulated","source":"synthetic"}

@app.post("/fit")
def fit(request:FitRequest,authorization:str|None=Header(default=None)):
    from .web_api import authorize, consume, mapped_errors
    settings=authorize(authorization)
    with mapped_errors():
        consume(settings,"fit",20)
        rag=None
        try:
            from .deploy_retrieval import ImmutableVectorIndex
            rag=RAGService(index_factory=ImmutableVectorIndex)
            result=rag.answer(request.query or " ".join(request.job.skills))
            return {"job_id":request.job.requisition_id,**result,"review_required":True}
        finally:
            if rag: rag.close()

from .web_api import install_console
install_console(app)
