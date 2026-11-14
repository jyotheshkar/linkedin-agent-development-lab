# Architecture maps

Start with system anatomy, then zoom into one request or one component. These maps separate development environment, runtime and future hosting. They do not assert a deployment or successful external integration.

| Diagram | Use | Source modules |
|---|---|---|
| [System anatomy](system-anatomy.svg) | Repository/Codespace versus Python runtime and future hosting | `application.py`, `service.py`, `workflow.py`, `atlas_lab.py` |
| [Request sequence](request-sequence.svg) | Validated job, real artifacts, exact review, simulation effects, ledger/projection | `contracts.py`, `application.py`, `provider.py`, `atlas_lab.py` |
| [RAG index/query](rag-index-query.svg) | Separate indexing from query, retained context and generation validation | `knowledge.py`, `retrieval.py`, `grounding.py`, `service.py` |
| [State/recovery](state-recovery.svg) | Failure categories, intent/receipt reconciliation and incomplete delivery | `workflow.py`, `provider.py`, `journal.py` |
| [Learning map](learning-map.svg) | Source-first investigation and optional isolated experiment | Lesson index, linked source/tests, `progress.py` |

SVG is the canonical rendered vector artifact. The matching PNG previews are generated from the same layout when Pillow is available. Editable source: [diagrams.py](diagrams.py).

```bash
python docs/architecture/diagrams.py
```

Arrows show data/control relationships, never inferred source trust or approval. Local state and optional Postgres are alternatives. `service.py` coordinates the RAG path; it is not merely the last box. Learner scoring is not part of each application request. A semantic retrieval test does not establish live generation.
