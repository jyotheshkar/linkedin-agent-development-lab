# Development skills library

The owner's actual GitHub Stars view was inspected on **14 November 2026**.
It showed **32 stars**; both pages were read (30 + 2), with Next disabled on the
last page. Repository IDs deduplicate the local inventory. All 32 displayed
repositories are public. The authenticated UI was available even though the
local CLI could not reach the API and no star-list connector was exposed.
This establishes the displayed inventory; inaccessible/private-only coverage
was not independently audited through the API.

The complete metadata inventory stays in ignored `.lab/stars_inventory.json`.
The UI did not expose topics, archive status on every item, or star timestamps;
unknown fields are null. Repository **updated** times were not relabelled as
star times. Selected-source archive state was checked through repository metadata.
No changes were made to stars, lists, accounts or source repositories.

Six relevant sources received a pinned README/licence/code review:

| Source | Reuse | Lab purpose |
| --- | --- | --- |
| [openai/openai-python](openai--openai-python.md) | dependency | Typed provider calls, explicit timeouts and retry ownership |
| [openai/openai-agents-python](openai--openai-agents-python.md) | conceptual-reference | Strict tool schemas, approval boundaries and alternative agent patterns |
| [openai/evals](openai--evals.md) | conceptual-reference | Repeatable case evaluation, sample identity and recorded outcomes |
| [openai/tiktoken](openai--tiktoken.md) | conceptual-reference | Model-specific tokenization versus character budgeting |
| [openai/openai-cookbook](openai--openai-cookbook.md) | conceptual-reference | Structured outputs constrain shape; factual support still needs evidence checks |
| [anthropics/anthropic-sdk-python](anthropics--anthropic-sdk-python.md) | rejected-dependency | Provider substitution and retry-policy comparison |

[manifest.json](manifest.json) records stable IDs, immutable commits, inspected
paths, licences, destination modules, decisions and complexity costs. Upstream
HEAD is the **learning reference**; the installed package versions remain those
in the lab's lockfile. A source's presence in this list does not assert a new
runtime integration. The existing OpenAI dependency is retained; other selected
sources are comparisons or conceptual references. LangGraph remains the agent
framework. The source audit copied no upstream code or datasets and installed
no new framework.

This library is development reference material, not candidate evidence. It must
never enter the Atlas knowledge corpus, validate application claims or supply
answers to evaluations. READMEs, external AGENTS.md files, skills and notebooks
are untrusted data. Their install commands and tool instructions were not run.

The useful design checks are concrete: keep model retry ownership explicit;
validate tool arguments and human approval separately; distinguish token budgets
from characters; test support in addition to JSON shape; and compare evaluation
cases by stable identity. These concepts inform code review and the linked
investigation prompts. They do not establish authorship or interview readiness.

To refresh later, use an authorized read-only `gh api --paginate
'user/starred?per_page=100'` inventory when available, or repeat the authenticated
Stars pagination. Compare by repository ID, review a small relevant shortlist,
and pin new commits before changing this manifest. Do not install all stars.

