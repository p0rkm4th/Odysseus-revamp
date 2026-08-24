# Hades feature matrix

Status is intentionally conservative: `green` means the current acceptance
evidence is real, `partial` means useful backend capability exists but the
product workspace or dogfood gate is incomplete.

| Domain | Backend | Capabilities/routing | UI/windows/search | Tests | Live dogfood | Status / next gap |
|---|---|---|---|---|---|---|
| Self/continuity | present | present | partial | green | partial | strengthen deterministic referent resolution; self dossier |
| Work/Life | present | partial | partial | green | partial | Life overview, reviews, commitments |
| Memory | present | present | partial | green | partial | layer and token inspector |
| Notifications/monitors | partial | partial | partial | partial | not accepted | canonical attention queue |
| Household | present | partial | partial | green | not accepted | intake, dossier, history, provenance |
| IT Assets/CMDB | present | present | partial | green | partial | reconciliation and detail workspace |
| Network | present | green | partial | green | green | change detection, history, polished map |
| Homelab | present | green for discovery | partial | green | green discovery | operation catalog and health surface |
| Security | present | partial | partial | green | not accepted | end-to-end authorized assessment dogfood |
| OSINT | present | partial | partial | green | not accepted | case dossier, graph/timeline |
| Business/CRM | partial | partial | partial | partial | not accepted | canonical Work-linked CRM workspace |
| Telegram | present | present | transport | green | partial | cross-channel continuity and voice |
| Voice/multimodal | partial | partial | partial | partial | not accepted | reviewable intake and PTT flow |
| Email/calendar/contacts | present | partial | present | green | credentials-dependent | shared entity links and integration center |
| Documents | present | partial | partial | green | not accepted | reusable attachments/dossiers |
| Models/routing | present | present | partial | green | partial | model lab and qualification evidence |
| Improvements | present | partial | partial | green | not accepted | registry workspace and promotion evidence |
| Developer/health/authority | present | partial | partial | green | partial | permissions, trace, backup projections |
| Shell/window/design system | present | partial | partial | partial | browser review pending | app-wide uniformity pass |

This matrix is a continuation artifact, not a claim that partial domains are
complete.
