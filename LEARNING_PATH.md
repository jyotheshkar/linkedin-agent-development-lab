# Learn through a working system

Use **visual architecture -> concrete execution -> annotated code -> small experiment -> tests -> interview explanation**. `main` is complete; experiments are optional and isolated. Learning is untimed unless requested.

| Order | Lesson | Main question |
|---|---|---|
| 1 | [ANATOMY-01](docs/learning/01-anatomy.md) | Where do development tools end and runtime begin? |
| 2 | [CONTRACTS-01](docs/learning/02-contracts.md) | Why is decoded JSON not yet a valid job? |
| 3 | [AGENT-01](docs/learning/03-agent-control.md) | Who grants permission to a proposed call? |
| 4 | [WORKFLOW-01](docs/learning/04-workflow-recovery.md) | What survives an unknown outcome/restart? |
| 5 | [ATLAS-01](docs/learning/05-atlas-lab.md) | Which source version is eligible and why? |
| 6 | [RAG-01](docs/learning/06-ingestion.md) | What must each chunk remember? |
| 7 | [RETRIEVAL-01](docs/learning/07-retrieval.md) | When should the nearest result be excluded? |
| 8 | [GROUNDING-01](docs/learning/08-grounding.md) | Which evidence actually reached the model? |
| 9 | [EVALUATION-01](docs/learning/09-evaluation.md) | What does each metric measure? |
| 10 | [DELIVERY-01](docs/learning/10-delivery.md) | How do interface, persistence and hosting differ? |

Each lesson links actual code, tests, diagrams, an experiment and L1/L2 discussion prompts. These are preparation examples, not known employer questions. Prerequisites offer help rather than gating the product.

If you say **"I am in contracts.py - what do I do?"**, the coach should read CONTRACTS-01, the current file and tests, show its request-diagram boundary, trace one input and offer one experiment. It should not recreate setup or provide a full syllabus.

Steer with `SIMPLER`, `WHY`, `TRACE`, `SHOW INPUT/OUTPUT`, `SHOW TEST`, `EXPERIMENT`, `HINT`, `QUIZ ME`, `DEEPER`, `CHECKPOINT`, `RESUME`, `PAUSE`.

For another chat without private access:

```bash
uv run l1-lab context-export --lesson CONTRACTS-01 --output .lab/context.json
```

Review that bounded export before sharing. It is source context, not automatic memory or a private-data backup. See [CHAT_BOOTSTRAP.md](CHAT_BOOTSTRAP.md).

Keep system evaluation, optional experiment completion, independent mastery and recruitment outcome distinct. A fresh correctly explained transfer change is stronger evidence than repeating a displayed solution. Only observed attempts update personal learning metrics.
