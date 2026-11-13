from __future__ import annotations
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import sys
from .service import RAGService, FIXTURE, ROOT, workflow
from .resources import DATA_DIR


def emit(value): print(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False))


def main(argv=None):
    p=argparse.ArgumentParser(description="L1 learning lab: all external effects simulated")
    commands=p.add_subparsers(dest="command",required=True)
    commands.add_parser("doctor")
    for name in ("demo","evaluate"):
        cmd=commands.add_parser(name)
        cmd.add_argument("--mode",choices=["offline","semantic","live"],default="offline")
        cmd.add_argument("--snapshot",type=Path,default=FIXTURE)
        if name=="demo": cmd.add_argument("--query",default="Python evaluation")
    run=commands.add_parser("run")
    run.add_argument("--goal",default="prepare application")
    run.add_argument("--job",type=Path,default=DATA_DIR/"job.json")
    run.add_argument("--snapshot",type=Path,default=FIXTURE)
    run.add_argument("--mode",choices=["offline","semantic"],default="offline")
    run.add_argument("--planner",choices=["offline","live"],default="offline")
    run.add_argument("--generation",choices=["offline","live"],default="offline")
    run.add_argument("--root",type=Path,default=Path(".lab"))
    resume=commands.add_parser("resume")
    resume.add_argument("run_id");resume.add_argument("--approve",action="store_true")
    resume.add_argument("--root",type=Path,default=Path(".lab"))
    trace=commands.add_parser("trace");trace.add_argument("run_id");trace.add_argument("--root",type=Path,default=Path(".lab"))
    imp=commands.add_parser("import-snapshot");imp.add_argument("file",type=Path)
    export=commands.add_parser("export-progress");export.add_argument("--output",type=Path,default=Path(".lab/checkpoint.json"))
    export.add_argument("--attempts",type=Path)
    args=p.parse_args(argv)
    try:
        if args.command=="doctor":
            packages={}
            for name in ["pydantic","pytest","langgraph","fastembed","qdrant-client","fastapi","openai"]:
                try: packages[name]=importlib.metadata.version(name)
                except importlib.metadata.PackageNotFoundError: packages[name]="MISSING"
            emit({"python":sys.version.split()[0],"packages":packages,
                  "default_data":"synthetic","external_effects":"simulation only",
                  "live_credentials_configured":bool(os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_MODEL")),
                  "student_tasks":"12 on main; inspect ASSIGNMENT.md","competence":"unmeasured"})
        elif args.command in ("demo","evaluate"):
            mode="semantic" if args.mode=="live" else args.mode
            rag=RAGService(args.snapshot,mode=mode,generation="live" if args.mode=="live" else "offline")
            try:
                if args.command=="demo": emit(rag.answer(args.query))
                else:
                    from .evaluation import evaluate
                    cases=json.loads((DATA_DIR/"eval_cases.json").read_text(encoding="utf-8"))
                    report=evaluate(rag.index,rag.generator,cases)
                    report["retrieval_mode"]=mode;report["generation_mode"]=rag.generator.mode
                    emit(report)
            finally: rag.close()
        elif args.command=="run":
            from .contracts import parse_job
            job=parse_job(args.job.read_text(encoding="utf-8"))
            rag=RAGService(args.snapshot,args.mode,args.generation)
            try: emit(workflow(args.root,args.goal,job,args.planner,rag).start(args.goal))
            finally: rag.close()
        elif args.command=="resume":
            from .workflow import Workflow
            emit(Workflow(args.root).resume(args.run_id,approved=args.approve))
        elif args.command=="trace":
            from .journal import Journal
            emit(Journal(args.root/"runs").load(args.run_id)["trace"])
        elif args.command=="import-snapshot":
            from .knowledge import load_snapshot, select_records
            snapshot=load_snapshot(args.file);selected=select_records(snapshot)
            if snapshot["kind"]!="atlas_snapshot": raise ValueError("import requires kind atlas_snapshot")
            destination=Path("private/atlas_snapshot.json");destination.parent.mkdir(exist_ok=True)
            shutil.copyfile(args.file,destination)
            emit({"path":str(destination),"selected_records":len(selected),"revision":snapshot["revision"],"continuous_sync":False})
        elif args.command=="export-progress":
            from .progress import export_checkpoint
            attempts=json.loads(args.attempts.read_text()) if args.attempts else []
            emit(export_checkpoint(args.output,attempts))
        return 0
    except NotImplementedError as exc:
        emit({"status":"unfinished_student_task","detail":str(exc),"next":"Read ASSIGNMENT.md; complete the named function and rerun its milestone tests."})
        return 2
    except (ValueError,OSError) as exc:
        emit({"status":"error","detail":str(exc)})
        return 1


if __name__=="__main__": raise SystemExit(main())
