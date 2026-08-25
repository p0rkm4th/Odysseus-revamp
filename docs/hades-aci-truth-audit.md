# Hades ACI truth audit

| Claim | State | Evidence |
|---|---|---|
| Current branch/repository recovery | SOURCE | `dbaddbda`, live compose inspection |
| Existing canonical read/Run foundations | FOCUSED_TESTED | 130 focused tests |
| ACI contract projections | FOCUSED_TESTED | `tests/test_aci_contracts.py` |
| Qwen live baseline | PARTIAL | 3-case subset; 2 provider errors |
| H0 vs final improvement | BLOCKED | final Decision-JSON path not yet wired/deployed |
| Exact ACI candidate deployed | OWNER_DOGFOOD_PENDING | running image predates local ACI changes |
| Runtime passive health | PASSIVE_LIVE_VERIFIED | compose, broker, Ollama bridge inspected |
| Owner GUI dogfood | OWNER_DOGFOOD_PENDING | owner-live script below |

No synthetic result is labeled as live owner evidence. No private runtime data,
database, backup, log, model blob, or owner Memory was added to the benchmark
artifacts.
