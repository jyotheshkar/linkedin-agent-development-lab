"""Explicit build probe, not a student score or a background job."""
from __future__ import annotations
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import tempfile
from l1_lab.contracts import Job
from l1_lab.service import RAGService, ROOT, workflow
from l1_lab.evaluation import evaluate
from l1_lab.progress import compute_metrics, DEFAULT_CONCEPTS

rag=RAGService()
try:
    cases=json.loads((ROOT/'data/eval_cases.json').read_text())
    report=evaluate(rag.index,rag.generator,cases)
    demo=rag.answer('Python evaluation')
    with tempfile.TemporaryDirectory() as td:
        runner=workflow(Path(td),'prepare Python evaluation application',
            Job(title='AI',company='Example Labs',requisition_id='SYNTHETIC-1',skills=['Python']),rag=rag)
        pending=runner.start('prepare Python evaluation application')
        completed=runner.resume(pending['run_id'],approved=True)
        execution={'initial_status':pending['status'],'final_status':completed['status'],
                   'completion':completed['completion'],'simulated_effect_count':runner.provider.effect_count()}
    result={'schema_version':1,'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            'python':platform.python_version(),'platform':platform.system(),
            'packages':{p:importlib.metadata.version(p) for p in ['langgraph','fastembed','qdrant-client','pydantic','fastapi','pytest','openai']},
            'evaluation':{'case_count':report['case_count'],'metrics':report['metrics'],'support_method':report['support_method']},
            'integrated_demo':{'source_kind':demo['source_kind'],'retrieval':demo['retrieval'],'generation':demo['generation'],
                               'answer_status':demo['answer']['status'],'context_chunk_count':len(demo['context_chunk_ids'])},
            'execution':execution,'initial_progress':compute_metrics([],DEFAULT_CONCEPTS),
            'live_planning':'not executed; optional credentials were not provisioned',
            'live_generation':'not executed; optional credentials were not provisioned'}
finally: rag.close()
destination=Path('verification/probe.json');destination.parent.mkdir(exist_ok=True)
destination.write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
