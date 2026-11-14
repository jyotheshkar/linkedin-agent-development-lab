# openai/openai-python

Verified starred on 14 November 2026 through the authenticated account's Stars
view. Repository ID: `307213173`. This public source was inspected at commit
`3dae6090cc31cc64a437fe0bcee740b6d81ed2cc`; it was not executed.

## Read the source

- [README.md](https://github.com/openai/openai-python/blob/3dae6090cc31cc64a437fe0bcee740b6d81ed2cc/README.md)
- [LICENSE](https://github.com/openai/openai-python/blob/3dae6090cc31cc64a437fe0bcee740b6d81ed2cc/LICENSE)
- [src/openai/_base_client.py](https://github.com/openai/openai-python/blob/3dae6090cc31cc64a437fe0bcee740b6d81ed2cc/src/openai/_base_client.py)

## Apply the idea

**Typed provider calls, explicit timeouts and retry ownership.** Retain the existing OpenAI SDK dependency. Inspect SDK retry behavior to explain why the lab disables SDK automatic retries and enforces its own call budget.

Lab destinations: `src/l1_lab/openai_adapter.py`, `tests/test_openai_adapter.py`.
Reuse decision: **dependency**. No source code or datasets were copied.

## Licence and cost

Apache-2.0. If future code copying is proposed, preserve upstream notices and
check the licence on the exact copied paths. Dependencies keep their packaged
licence notices. Remote calls incur provider cost; credentials and network are optional. The pinned upstream head is a learning reference, not the version in uv.lock.

## Investigation task

Find the lab's `max_retries=0` setting. Explain which layer owns a transport retry and why repeating a model call differs from repeating a simulated employer effect.

These are original lab investigation prompts. Reading upstream reference code
is assisted exposure and does not establish independent learner mastery.

