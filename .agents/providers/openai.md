# OpenAI/Codex Provider Mapping

Map the provider-independent classes as follows:

| Class | Recommended mapping |
|---|---|
| `strong` | Frontier GPT/Codex model, medium/high reasoning effort |
| `mid` | Balanced GPT/Codex model, medium reasoning effort |
| `cheap` | Mini/nano model or low-effort Codex |
| `reviewer` | Fresh frontier GPT/Codex model at high effort for initial or milestone review; resume that task for focused rechecks |

Choose the concrete model from the current provider catalogue. Do not rewrite
the routing contract when model names or availability change.
