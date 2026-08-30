# Generic Provider Mapping

For a provider without a dedicated adapter, select the best available model
for each capability class:

| Class | Requirement |
|---|---|
| `strong` | Best available reasoning/judgment model |
| `mid` | Competent general model with moderate reasoning |
| `cheap` | Lowest-cost model that passes the bounded task evals |
| `reviewer` | Fresh `strong`/high context for initial or milestone review; resume it for focused rechecks |

If the provider has no configurable effort setting, preserve the capability
class and record the provider's default effort as the effective value.
