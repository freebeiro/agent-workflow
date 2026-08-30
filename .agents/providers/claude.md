# Claude Provider Mapping

Map the provider-independent classes as follows:

| Class | Recommended mapping |
|---|---|
| `strong` | Opus, usually medium effort; high for decisions/high risk |
| `mid` | Sonnet, medium effort |
| `cheap` | Sonnet low/medium or Haiku where available |
| `reviewer` | Fresh Opus/high for initial or milestone review; resume that session for focused rechecks |

Model names and availability are provider configuration, not repository
authority. If a named model is unavailable, use the nearest capability class.
