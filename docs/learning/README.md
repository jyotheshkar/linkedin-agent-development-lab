# Code-linked learning system

Start with [ANATOMY-01](01-anatomy.md), then [CONTRACTS-01](02-contracts.md). The application is complete; optional experiments do not gate startup.

The versioned [lesson index](lesson-index.json), validated by [its JSON schema](lesson-index.schema.json), maps every lesson to actual source symbols, pytest targets, diagrams, JD areas and a safe experiment. Source annotations use those same lesson IDs. Update the mapping when code changes rather than relying on brittle line numbers.

```bash
uv run pytest tests/test_context_export.py -q
uv run l1-lab context-export --lesson CONTRACTS-01 --output .lab/context.json
```

A future assistant must open the exact file/tests before teaching. A private link does not imply access; the allowlisted, bounded export is the explicit fallback. It contains saved source context and revision metadata, not private snapshots or automatic memory.

Use `SIMPLER`, `WHY`, `TRACE`, `SHOW INPUT/OUTPUT`, `SHOW TEST`, `EXPERIMENT`, `HINT`, `QUIZ ME`, `DEEPER`, `CHECKPOINT`, `RESUME` or `PAUSE` to choose the next conversational step. Record observed learning only. System evaluation, experiment completion, independent mastery and recruitment outcome remain separate.
