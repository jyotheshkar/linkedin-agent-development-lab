# Evaluation and objective progress

The evaluation bank is separate from indexed knowledge. It contains synthetic
developer-labelled cases, not employer interview questions or an independent
expert truth set. The command reports each denominator and each case. Evaluation
exposes held-out labels for debugging; do not index the evaluation file.

| Measure | Numerator | Denominator |
| --- | --- | --- |
| Retrieval recall@k | Expected record IDs present in retrieved results | Expected record IDs across answerable cases |
| Citation validity | Citation references resolving to retrieved records/chunks | All citation references, including repetitions |
| Answer support | Claims extracted exactly from cited expected evidence, without labelled prohibited strings | All produced claims |
| Abstention accuracy | Unanswerable cases returning `abstain` and no claims | Unanswerable cases |
| Answerable coverage | Answerable cases producing at least one supported claim and `supported` status | Answerable cases |

Support is agreement with the labelled bank. Citation membership and exact quotes
do not establish semantic entailment. A copied negation or changed number can
still be false. Inspect these cases and add a human-reviewed claim-level bank
before making stronger claims. No model judge is used. Token and cost values are
`null` because this evaluator does not observe provider billing. Latency records
elapsed wall-clock time around actual calls, including retrieval and generation.

`compare_runs` pairs stable case IDs. Missing/new cases are explicit, duplicates
and non-finite/Boolean scores are errors. A score drop greater than tolerance is
a regression with a documented 1e-12 floating-point boundary allowance. No shared
cases yields `null` rates, not a successful release gate.

## Learning metrics

The canonical rubric is correctness 4, reasoning 2, boundaries/verification 2,
explanation 2. The serialized key for boundaries/verification is `boundaries`.
Only graded attempts enter accuracy denominators. Ungraded work, passing tests,
and reference implementation checks never create an explanation score.
Every graded attempt must explicitly declare `assisted: true` or
`assisted: false`. Missing declarations are rejected; absence of recorded
assistance never establishes independence. Hints, reference exposure, copied
reference code and the legacy `assistance` flag can additionally disqualify an
attempt from independent evidence.

| Measure | Formula |
| --- | --- |
| Knowledge accuracy | 100 × earned rubric points / available points |
| Independent knowledge accuracy | Same, only without hints, copied code or reference exposure |
| First-attempt accuracy | 100 × fully correct first attempts / graded first attempts, by question ID |
| Cumulative attempt accuracy | 100 × fully correct attempts / graded attempts |
| Coverage | 100 × selected concepts attempted / selected concepts |
| Mastery | 100 × concepts with two independent fully correct distinct scenarios, including transfer / selected concepts |

Fully correct requires 10/10 and no critical misconception. An assisted first
attempt remains marked assisted; an independent-only first-attempt measure is
reported separately. A later critical misconception clears previous mastery
evidence for that topic. Repeating a scenario does not count twice. The list of
attempts is chronological; preserve that order during import.

No attempts means accuracy is N/A (`null`), competence is unmeasured, and no
mastery evidence exists. These practice measures are not hiring probabilities.
Progress checkpoints retain raw question/variant IDs, rubric, assistance,
reference exposure, tests, source IDs and next action. Files use schema version
1 and belong under ignored `.lab/`; this app does not update Minister or Atlas.

The student task edits only `compare_runs` and `compute_metrics` in these modules.
Run `python -m pytest -m m6` and explain one missing-case regression and one
assisted-versus-independent metric example before a coach records understanding.
