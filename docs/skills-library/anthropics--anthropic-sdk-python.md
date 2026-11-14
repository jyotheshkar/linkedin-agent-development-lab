# anthropics/anthropic-sdk-python

Verified starred on 14 November 2026 through the authenticated account's Stars
view. Repository ID: `590187800`. This public source was inspected at commit
`5139cf2e7d07aa618a6c30b7e0c712f10ccb5ad9`; it was not executed.

## Read the source

- [README.md](https://github.com/anthropics/anthropic-sdk-python/blob/5139cf2e7d07aa618a6c30b7e0c712f10ccb5ad9/README.md)
- [LICENSE](https://github.com/anthropics/anthropic-sdk-python/blob/5139cf2e7d07aa618a6c30b7e0c712f10ccb5ad9/LICENSE)
- [src/anthropic/_base_client.py](https://github.com/anthropics/anthropic-sdk-python/blob/5139cf2e7d07aa618a6c30b7e0c712f10ccb5ad9/src/anthropic/_base_client.py)

## Apply the idea

**Provider substitution and retry-policy comparison.** Inspect the second provider's typed client/retry policy as an L2 trade-off. Avoid adding another live provider or claiming that its SDK is integrated.

Lab destinations: `docs/DECISIONS.md`, `src/l1_lab/openai_adapter.py`.
Reuse decision: **rejected-dependency**. No source code or datasets were copied.

## Licence and cost

Apache-2.0; historical MIT portions as documented in upstream README. If future code copying is proposed, preserve upstream notices and
check the licence on the exact copied paths. Dependencies keep their packaged
licence notices. Additional credentials, API costs, model contracts and retry semantics would expand scope.

## Investigation task

Describe the interface required to substitute another provider. Include structured-output shape, timeouts, retries, usage reporting and a test double before making a live call.

These are original lab investigation prompts. Reading upstream reference code
is assisted exposure and does not establish independent learner mastery.

