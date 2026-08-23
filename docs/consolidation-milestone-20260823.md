# Consolidation milestone lineage

This candidate is built from the current Hades worktree, not from a cherry-pick
or merge. The clean Hades baseline is `85297cee44f8c5b3aa4bbf54ab482f5f7513baa5`.
Recovered Omarchy evidence is `internal/antigravity-tracking@5292a88c309b2feab3c8ae71825fd38c350fa5f3` from the local bundle; its inventory, homelab, OSINT, approval, Telegram, economic-control, safe-improvement, and Jarvis benchmark behavior was adapted through current Hades bindings.

Current Hades exposes the recovered control-plane metadata and approval
surfaces. Telegram polling remains opt-in; external economic execution is not
wired. The improvement registry records candidates, evaluations, promotion
approvals, and rollback history, but does not load artifacts or replace
runtime behavior.

The current fasttrack security line is represented by the self-applying
`odysseus_fasttrack_*`, `odysseus_orchestration_*`, and related artifacts in the
worktree. No cleaner authoritative source was found in the bounded relevant
history, bundles, or recovery directories. It is policy/orchestration evidence,
not a complete pentest product.

## Safety boundaries

- CMDB owns technical identity, observations, reconciliation, and provenance.
- Inventory owns owner-approved items, stock, recipes, and review drafts.
- `src/cmdb_inventory_adapter.py` emits pending proposals only; confirmation is
  still required before inventory mutation.
- IP addresses never establish identity by themselves.
- Economic execution and autonomous improvement artifact loading remain disabled.
- Full security-assessment execution remains deferred.
