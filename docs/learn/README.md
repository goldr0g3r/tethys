# Learn

Long-form explainers that build from "I've never heard of this" to "I can read the ADRs and understand the trade-offs". Each piece is self-contained and assumes only general embedded / networking / Python literacy.

Where runbooks teach *how to operate* the Tethys repo (step-by-step recipes) and ADRs record *one decision each*, the explainers here teach *concepts* — the protocols, standards, and engineering practices the repo is built on.

| # | Explainer | Scope | Audience | Status |
| - | --- | --- | --- | --- |
| 1 | [xcp-101.md](xcp-101.md) | XCP from first principles — master/slave model, CTO/DTO, DAQ/ODT, CAL/PAG, STIM, A2L, transports, seed-and-key, loss handling, session walk-through, glossary. | Engineer who has never touched XCP. | Drafted in `docs/xcp-101-explainer` |

## How explainers are written

- **Audience:** an engineer who knows their domain (embedded / networking / Python) but has never heard of the specific topic. No prerequisites beyond general literacy.
- **Length budget:** 8,000-12,000 words for a 101-class explainer; longer is fine for deep-dives.
- **Style:** dense and technically accurate; respectful of the reader's intelligence; not "fluffy intro". Aim for the tone of a high-quality engineering blog (Cloudflare blog, Stripe engineering).
- **Diagrams:** Mermaid, rendered inline by GitHub. No SVG export required.
- **Citations:** Every primary-source claim cites either a Tethys standards-matrix S-ID (`docs/research/phase-0-standards-matrix.csv`) or a retrieval-dated URL.
- **Tethys context:** Every explainer ends with a "How Tethys uses this — a quick map" section that points at the relevant ADRs and code paths.

## Planned future explainers

These are *aspirational* — they will be added as the matching phases ship and as time permits.

| Topic | Why | Likely phase |
| --- | --- | --- |
| A2L deep-dive | Format internals, IF_DATA extensions, A2L generation from linker map. | Phase 2 + Phase 7 |
| MISRA C:2023 cheatsheet | Mandatory + Required + Advisory rule overview; common-violation patterns; deviation procedure. | Phase 0 (after PR-5 lands) |
| CCSDS primer (TC/TM/COP-1) | Space-link reliability layer that wraps XCP in the space profile. | Phase 8 |
| AUTOSAR E2E primer | Fault-class vocabulary that safety reviewers use; Tethys's mechanism mapping. | Phase 10 |
| IEC 61508 / ISO 26262 essentials | PFH, SIL/ASIL, residual-error budgets — the maths behind ADR-0010. | Phase 10 |
| ECSS-E-ST-40C Rev.1 SDLC | What ECSS asks for; which artefacts Tethys produces; gaps. | Phase 8 + Phase 10 |

## How explainers are added

1. Open an Issue with label `type/docs` + `area/docs` and (optionally) the relevant `phase/*` label.
2. If the explainer is large (>3,000 words), draft a sub-plan via `CreatePlan` (per parent-plan §6.8). Smaller explainers can land without a sub-plan.
3. Land the explainer **plus** a research note (`docs/research/phase-<N>-<topic>-learn-execution.md`) in the same PR.
4. Add the row above and tick "Status" once merged.
5. Link the new explainer from the root [`README.md`](../../README.md) "Learn" section.

## Cross-references

- Parent plan: [`.cursor/plans/xcp_extreme-env_tool_14019278.plan.md`](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md)
- Architecture: [`docs/architecture/system-context.md`](../architecture/system-context.md)
- ADRs: [`docs/adr/README.md`](../adr/README.md)
- Runbooks: [`docs/runbooks/README.md`](../runbooks/README.md)
- Research notes: [`docs/research/`](../research/)
- Standards matrix: [`docs/research/phase-0-standards-matrix.csv`](../research/phase-0-standards-matrix.csv)
