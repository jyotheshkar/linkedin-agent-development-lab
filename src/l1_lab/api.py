"""Local REST exercise; optional bearer token, no outbound provider writes."""
import hmac
import os
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, ConfigDict, Field
from .contracts import Job
from .service import RAGService

app=FastAPI(title="L1 simulated fit API",version="0.1.0")

class FitRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    job: Job
    query: str | None = Field(default=None,min_length=1,max_length=2000)

@app.get("/health")
def health(): return {"status":"ok","effects":"simulated","source":"synthetic"}

@app.post("/fit")
def fit(request:FitRequest,authorization:str|None=Header(default=None)):
    token=os.getenv("LAB_API_TOKEN")
    if token and (not authorization or not hmac.compare_digest(authorization,"Bearer "+token)):
        raise HTTPException(401,"Bearer token required")
    rag=None
    try:
        rag=RAGService()
        result=rag.answer(request.query or " ".join(request.job.skills))
        return {"job_id":request.job.requisition_id,**result,"review_required":True}
    except NotImplementedError as exc:
        raise HTTPException(409,"Unfinished student task: "+str(exc)) from exc
    finally:
        if rag: rag.close()
