# openai/evals

Verified starred on 14 November 2026 through the authenticated account's Stars
view. Repository ID: `592489166`. This public source was inspected at commit
`8eac7a7de5215c907fbddc30efdaf316913eccdd`; it was not executed.

## Read the source

- [README.md](https://github.com/openai/evals/blob/8eac7a7de5215c907fbddc30efdaf316913eccdd/README.md)
- [LICENSE.md](https://github.com/openai/evals/blob/8eac7a7de5215c907fbddc30efdaf316913eccdd/LICENSE.md)
- [evals/eval.py](https://github.com/openai/evals/blob/8eac7a7de5215c907fbddc30efdaf316913eccdd/evals/eval.py)

## Apply the idea

**Repeatable case evaluation, sample identity and recorded outcomes.** Use stable lab case IDs, explicit denominators and distinct retrieval/citation/support metrics. Do not import upstream datasets or install this evaluation framework.

Lab destinations: `src/l1_lab/evaluation.py`, `data/eval_cases.json`.
Reuse decision: **conceptual-reference**. No source code or datasets were copied.

## Licence and cost

MIT for code; dataset-specific exceptions. If future code copying is proposed, preserve upstream notices and
check the licence on the exact copied paths. Dependencies keep their packaged
licence notices. Full registry uses Git LFS and model calls may cost money. Local lab cases stay outside the retrieval corpus.

## Investigation task

Pick one lab evaluation case. Trace its case ID through the report, then explain why retrieval recall, citation membership and labelled answer support need separate denominators.

These are original lab investigation prompts. Reading upstream reference code
is assisted exposure and does not establish independent learner mastery.

