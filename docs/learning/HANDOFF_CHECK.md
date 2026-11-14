# Fresh-chat fallback check

**Checked:** 14 November 2026. This is a source-context handoff check, not a learner assessment or an application test result.

## Export and environment

The documented learner command is:

```bash
uv run l1-lab context-export --lesson CONTRACTS-01 --output .lab/context.json
```

During this host check, `uv run` could not persist an interpreter-cache file because the sandbox denied that cache path. That CLI attempt did not complete. The same actual exporter was then invoked directly under the available host Python **3.11.15**, without installing dependencies or changing runtime code:

```python
import sys
from pathlib import Path

root = Path(r"C:\workspace\linkedin-atlas-l1-lab")
sys.path.insert(0, str(root / "src"))
from l1_lab.context_export import export_context

export_context(
    "CONTRACTS-01",
    root / ".lab/handoff-contracts-context.json",
    root,
)
```

This successfully produced a **9,846-byte** JSON bundle containing three allowlisted files. It recorded repository ID **1456774523**, canonical URL `https://github.com/jyotheshkar/linkedin-agent-development-lab`, commit `4f5c9b407bfa99456f88185d223c17ee548c49c9`, and `worktree_dirty=true`. The export captures saved local bytes; it must not be described as an exact pristine copy of that commit. This host check does not verify the project's Python 3.12 installation or replace the Codespace/CLI verification report.

Bundle SHA256: `611e94d3bd941f80a6822e4be3044bb77bc5665d1c3b55f1dafd1141d8bb3d8a`.

## Inspection using only the exported content

After creation, the check loaded only the JSON bundle. It did not reopen the repository source/tests to fill missing context.

| Exported content | Observed handoff evidence |
|---|---|
| `src/l1_lab/contracts.py` | Complete `Job`, `parse_job` and `normalize_identity` definitions, including validators, imports, contracts and implementation bodies; no `NotImplementedError` in those definitions |
| `tests/test_contracts.py` | Concrete valid job fixture; malformed/wrong-shape inputs; Boolean/string/out-of-range budgets; Unicode/whitespace/case normalization; duplicate identity and unchanged caller set |
| `docs/learning/02-contracts.md` | Component context, concrete input, optional isolated experiment, exact test command, L1/L2 discussion and limitations |
| Lesson metadata | All three declared test node IDs found in the exported test AST; source/test paths and diagram references retained |
| Revision and privacy metadata | Canonical repository identity, commit/dirty state, source hashes, explicit allowlist/redaction declaration |
| Minimal checkpoint | Empty attempts and `readiness="unmeasured"`; no invented learner grade |

The available content is sufficient for a fresh coach to trace:

1. The exported valid fixture through JSON decoding into a dictionary and strict `Job` validation, including default `max_calls=8`.
2. `max_calls=true` to the strict integer rejection boundary, using the linked public test.
3. A whitespace/case/fullwidth-character identity to `example labs::r-1`, then the duplicate check without mutating `seen`.

These are source/test inspection findings. No pytest suite or learner explanation was graded by this check.

## Limits and next-chat behavior

A private repository or Codespace link does not grant a future assistant access. Attach the reviewed JSON when access is unavailable. The bundle includes diagram **references**, not the SVG bytes; a coach without repository access can describe the component from the exported lesson/source, or request only the relevant diagram if needed.

The export is a saved-file snapshot, not automatic memory, a live workspace connection or a backup of private progress. It does not contain unsaved editor changes, the whole repository, `.env`, private Atlas snapshots or raw logs. Its redaction/allowlist metadata is not a universal proof that arbitrary future source files cannot contain sensitive text; review each export before sharing.

Start the fresh chat with one concept, one concrete trace and one small experiment. Keep assistance/reference exposure explicit. Software correctness, handoff sufficiency and independent learner competence remain separate claims.
