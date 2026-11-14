# openai/openai-agents-python

Verified starred on 14 November 2026 through the authenticated account's Stars
view. Repository ID: `946380199`. This public source was inspected at commit
`64fbde5d02b42ae5f9db668eb0184cdb3fc9d775`; it was not executed.

## Read the source

- [README.md](https://github.com/openai/openai-agents-python/blob/64fbde5d02b42ae5f9db668eb0184cdb3fc9d775/README.md)
- [LICENSE](https://github.com/openai/openai-agents-python/blob/64fbde5d02b42ae5f9db668eb0184cdb3fc9d775/LICENSE)
- [src/agents/tool.py](https://github.com/openai/openai-agents-python/blob/64fbde5d02b42ae5f9db668eb0184cdb3fc9d775/src/agents/tool.py)

## Apply the idea

**Strict tool schemas, approval boundaries and alternative agent patterns.** Compare function-tool contracts and human review. Preserve LangGraph rather than adding a second orchestration framework.

Lab destinations: `src/l1_lab/agent.py`, `src/l1_lab/workflow.py`.
Reuse decision: **conceptual-reference**. No source code or datasets were copied.

## Licence and cost

MIT. If future code copying is proposed, preserve upstream notices and
check the licence on the exact copied paths. Dependencies keep their packaged
licence notices. No dependency added. SDK integration would increase abstractions and duplicate the current executor.

## Investigation task

Trace one call through `validate_tool_call` and `Workflow._graph_step`. Identify the points at which a proposal becomes permitted and a simulated effect becomes approved.

These are original lab investigation prompts. Reading upstream reference code
is assisted exposure and does not establish independent learner mastery.

