"""Evaluate fresh developer-authored cases without retuning the frozen threshold."""
import json
from pathlib import Path
from l1_lab.evaluation import evaluate
from l1_lab.service import RAGService
from l1_lab.resources import DATA_DIR

if __name__ == "__main__":
    rag = RAGService()
    try:
        report = evaluate(rag.index, rag.generator, json.loads((DATA_DIR / "eval_holdout.json").read_text()))
    finally:
        rag.close()
    report["scope"] = "Four developer-authored fresh scenarios; not an independent external benchmark. Threshold unchanged at 0.3."
    output = Path(".lab/eval-holdout.json")
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"path": str(output), "metrics": report["metrics"], "scope": report["scope"]}))
