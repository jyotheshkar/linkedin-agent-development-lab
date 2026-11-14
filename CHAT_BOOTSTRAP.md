# Start a source-grounded coaching chat

Paste this message with the current repository URL, observed Codespace address if useful, and optional context/checkpoint. A link alone does not guarantee private access.

> This is my **LinkedIn Agent Development Lab**, stable repository ID **1456774523**, owner **jyotheshkar**. Resolve its current URL and actual branch/commit; preserve unsaved edits. `main` is the complete working application and reference-code exposure is authorized. Read `START_HERE.md`, `AGENTS.md`, `COACH_HANDOVER.md` and CONTRACTS-01 in `docs/learning/lesson-index.json`, then open `src/l1_lab/contracts.py` and its linked tests. I am studying contracts.py. Show its place in the architecture, explain one concept, trace one input and give one small isolated experiment. The MVP was built with assistance; do not infer my competence from its tests. Use my checkpoint if supplied and distinguish committed source from unsaved edits. Learning is untimed unless I ask. If private access is missing, use the context export I attach or ask only for minimal relevant content; do not pretend the link was read.

The repository was identified during prompt preparation as `https://github.com/jyotheshkar/linkedin-atlas-l1-lab-2026`. Resolve its stable ID after a rename rather than assuming this name/commit/runtime is unchanged.

## Access fallback

In the actual checkout:

```bash
uv run l1-lab context-export --lesson CONTRACTS-01 --output .lab/context.json
```

Review and attach that file. It provides allowlisted, bounded source/lesson/test context and revision metadata, not `.env`, credentials, private Atlas data, whole logs or the entire repository. It is not automatic cross-chat memory. An export captures saved files; describe unsaved editor changes separately.

Steer one step with `SIMPLER`, `WHY`, `TRACE`, `SHOW INPUT/OUTPUT`, `SHOW TEST`, `EXPERIMENT`, `HINT`, `QUIZ ME`, `DEEPER`, `CHECKPOINT`, `RESUME`, `PAUSE`.
