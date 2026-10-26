# Meta API facts

Owned by the engine package. Tag every row **measured** (we called it; date and request shown),
**press** (published; source named) or **unverified**. A measured row supersedes a press row; the
press row is struck, never edited to match.

| Question | Answer | Tag | Date |
|---|---|---|---|
| Endpoint shape (OpenAI-compatible?) | base `https://api.meta.ai/v1`; Meta's examples use the OpenAI SDK; Responses, Chat Completions, Messages listed | press (dev.meta.ai/docs/models) | 2026-10-24 |
| Streaming on chat | not stated | unverified | - |
| Model ids (Muse) | `muse-spark-1.3` (recommended), `-1.2`, `-1.1`, `muse-wonder-1.0`; `-contributor` ids train on content and are never used | press | 2026-10-24 |
| Llama on the same key? | not stated | unverified | - |
| SAM offered on the API? | `sam-3.1` via `POST /v1/responses` | press | 2026-10-24 |
| Prices | Spark $1.25 in / $0.15 cached / $4.25 out per 1M tokens; Wonder $4 / $0.20 / $20 | press (dev.meta.ai/docs/pricing-rate-limits) | 2026-10-24 |
| Rate limits | Spark and Wonder 3,000 req/min, 4M tok/min, per team | press | 2026-10-24 |
