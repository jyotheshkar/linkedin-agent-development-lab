"""Conservative UTF-8 byte budgeting for optional live-model inputs.

LEARN: GROUNDING-01. This is an upper-bound estimate for byte-level tokenizers,
not observed usage or a substitute for a provider/model tokenizer. Unknown model
limits require an explicit operator-supplied limit; output and framing reserve
are removed before admitting user/context bytes.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ContextBudget:
    context_tokens: int = 32768
    output_tokens: int = 1800
    framing_reserve: int = 2048

    def check(self, instructions: str, user_input: str) -> dict:
        if any(type(x) is not int or x <= 0 for x in (self.context_tokens, self.output_tokens, self.framing_reserve)):
            raise ValueError("model context budget must contain positive integers")
        estimated = len((instructions + user_input).encode("utf-8"))
        available = self.context_tokens - self.output_tokens - self.framing_reserve
        if estimated > available or available <= 0:
            raise ValueError("input exceeds the conservative model budget; reduce context")
        return {"method": "UTF-8 bytes as conservative token upper bound", "input_estimate_upper_bound": estimated,
                "configured_context_limit": self.context_tokens, "output_headroom": self.output_tokens,
                "framing_reserve": self.framing_reserve, "observed_input_tokens": None}
