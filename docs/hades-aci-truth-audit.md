# Hades ACI truth audit

| Claim | State | Evidence |
|---|---|---|
| Current branch/repository recovery | SOURCE | `dbaddbda`, live compose inspection |
| Existing canonical read/Run foundations | FOCUSED_TESTED | 130 focused tests |
| ACI contract projections | FOCUSED_TESTED | `tests/test_aci_contracts.py` |
| Qwen live baseline | PARTIAL | 15-case subset; success 0.20, weighted 0.4333; 9 provider errors |
| H0 vs final improvement | PARTIAL | final 15-case ACI weighted `0.6667` vs H0 `0.4333`; synthetic only |
| Chat route ACI mode | FOCUSED_TESTED | explicit `hades_aci_mode` setting passed to canonical loop; default `aci`, reversible |
| Frozen evaluation corpus | SOURCE | 120 synthetic cases: 96 development, 24 held-out, 12 canary |
| Exact ACI candidate deployed | DEPLOYED | `odysseus:candidate-1ce7ec34b9f7`; `/api/version` source/build/frontend match |
| Runtime passive health | PASSIVE_LIVE_VERIFIED | compose, broker, Ollama bridge inspected |
| Owner GUI dogfood | OWNER_DOGFOOD_PENDING | owner-live script below; authentication and owner data remain out of automation scope |

## Final runtime checkpoint

- Full regression: `6292 passed, 3 skipped, 186 warnings`.
- App health: `/api/health` healthy.
- Broker: user service active; socket `660 scootz:scootz`.
- Ollama: bridge healthy; `qwen3:8b` available.
- ChromaDB and SearXNG: running; SearXNG healthy.
- Candidate source/build/frontend provenance: matched.
- Image retention: current candidate and previous `odysseus:candidate-dbaddbdaac7e` retained; no cleanup performed.
- Final H0-equivalent ACI: 15 cases, `0.4667` success, `0.6667` weighted; 11 clean, 4 timeouts.
- Improvement is synthetic benchmark evidence, not owner-live evidence.

No synthetic result is labeled as live owner evidence. No private runtime data,
database, backup, log, model blob, or owner Memory was added to the benchmark
artifacts.

## Owner-live script

1. What do you remember about me?
2. What am I working on?
3. What IT assets do I have?
4. Tell me more about the first physical machine.
5. What network am I currently connected to?
6. Do a deep dive on my local network. (Must fail closed until safe scope is explicitly authorized.)
7. What's running in Odysseus?
8. Start a harmless persistent task, then say Continue.
9. Switch Qwen -> Luna -> Sol -> Qwen during that Run and continue.
10. Diagnose/fix a safe synthetic repository defect under Workspace YOLO, if enabled.
