"""Provided integration wiring; student functions stay in their focused modules."""
from __future__ import annotations
import json
from pathlib import Path
from .knowledge import load_snapshot, select_records, chunk_records
from .retrieval import VectorIndex
from .grounding import build_context, validate_answer, OfflineGenerator

from .resources import ROOT, DATA_DIR
FIXTURE = DATA_DIR / "synthetic_snapshot.json"


class RAGService:
    def __init__(self, snapshot=None, mode="offline", generation="offline", index_factory=None):
        snapshot = Path(snapshot or FIXTURE)
        self.snapshot = load_snapshot(snapshot)
        if generation == "live" and self.snapshot["kind"] != "synthetic":
            raise ValueError("Live demonstrations require the synthetic fixture")
        records = select_records(self.snapshot)
        self.index = (index_factory or VectorIndex)(chunk_records(records),mode=mode)
        self.generator = OfflineGenerator()
        if generation == "live":
            from .openai_adapter import OpenAIAnswerGenerator
            self.generator = OpenAIAnswerGenerator()
        self.last = None

    def answer(self, query: str, top_k=3, min_score=.3, max_chars=3000) -> dict:
        from time import perf_counter
        started=perf_counter()
        hits=self.index.search(query,top_k=top_k,min_score=min_score)
        context=build_context(hits,max_chars=max_chars)
        retained={c["chunk_id"] for c in json.loads(context)["chunks"]} if context else set()
        used=[h for h in hits if h["chunk_id"] in retained]
        answer=validate_answer(self.generator.generate(query,used),used)
        self.last={"query":query,"source_kind":self.snapshot["kind"],
            "retrieval":self.index.manifest,"generation":self.generator.mode,
            "retrieved_chunks":hits,"context_chunk_ids":sorted(retained),
            "context":context,"answer":answer,"latency_seconds":perf_counter()-started}
        return self.last

    def close(self): self.index.close()


def workflow(root,goal,job=None,planner_mode="offline",rag=None,journal=None,provider=None,capture_evidence=False):
    from .contracts import normalize_identity
    from .planner import OfflinePlanner
    from .workflow import Workflow
    target=normalize_identity(job.company,job.requisition_id) if job else None
    planner=OfflinePlanner(target_identity=target)
    if planner_mode == "live":
        from .openai_adapter import OpenAIPlanner
        planner=OpenAIPlanner()
    # Retrieved evidence only enters outputs, never the planner's permission state.
    cache={}
    def retrieve(args,key):
        result=rag.answer(args["query"])
        cache.update(result)
        output = {"source_ids":result["context_chunk_ids"],"answer":result["answer"],"kind":result["source_kind"]}
        if capture_evidence:
            output["evidence"] = result
        return output
    def draft(args,key):
        if not cache:
            raise ValueError("draft requires retrieved evidence in this integrated demo")
        return {"draft":cache["answer"],"source_ids":cache["context_chunk_ids"],"review_required":True}
    return Workflow(Path(root),planner=planner,max_calls=job.max_calls if job else 8,
                    evidence_fn=retrieve if rag else None,draft_fn=draft if rag else None,
                    journal=journal,provider=provider)
