# CLINE MASTER DIRECTIVE: Autonomous Emergent Society & Economic Simulation

## 1. Project Context & Role
You are working on an existing, functional **offline Python/Pygame economic simulation game**.
- **Do NOT rewrite the game from scratch.** Inspect the repository first and evolve existing systems incrementally.
- **Core Objective:** Transform the simulation into an offline, open-ended autonomous society and economy where behaviors, businesses, contracts, and institutions emerge from agent interactions rather than hardcoded progression scripts.

---

## 2. Current Implementation Status
- **[DONE] Initial Audit & Architecture Roadmap:** Codebase audited (`main.py`, `systems/ekonomi_core.py`, `game/*`, `tests/*`). Baseline: 44 tests passing, ~1.18s for 40 citizens × 1,100 days (seed 42).
- **[DONE] Phase 1 — Centralized Accounting Ledger:** Implemented (`systems/accounting.py` + gradual migration). See `02_PHASE_1_ACCOUNTING_LEDGER.md` for invariants that **must never be broken** in later phases.
- **[NEXT] Phase 2 — Organic Economy, Goods, Contracts & Macro Metrics:** Ready to execute (`03_PHASE_2_ORGANIC_ECONOMY_AND_MARKETS.md`).
- **[PENDING] Phases 3–9:** Execute strictly one phase at a time (`04_...` through `10_...`).

---

## 3. Non-Negotiable Engineering & Design Rules
1. **Strict Accounting Integrity:** Every monetary transfer must go through the centralized ledger with balanced debits and credits. Never mutate `cash`, `savings`, `treasury`, or debt balances directly. Money cannot appear out of thin air unless explicitly defined as central bank / monetary policy creation.
2. **Offline-First & Hardware-Aware:** 100% offline execution. **Do NOT add external LLM APIs, cloud services, vector DBs, or heavy deep-learning frameworks (no PyTorch/TensorFlow).** Prefer Python standard library, sparse graphs, tabular/Bayesian/contextual models, and bounded search. Target smooth performance at up to **140 citizens**.
3. **Preserve Player Philosophy:** The player is an observer and partial policy/market intervenor—**NOT** a city-builder micromanaging individual citizens. Preserve all existing UI controls and player mechanics.
4. **Pickle Save Compatibility:** `World` and `Citizen` are serialized via `pickle` in `main.py`. Never rename/move legacy classes without a backward-compatible alias, and keep `World.migrate_save()` idempotent.
5. **No Artificial Civilization Unlocks:** Do NOT gate businesses, banks, contractors, or organizations behind fixed year thresholds, population milestones, or scripted unlock events. Institutions must emerge from resources, capital, contracts, and agent decisions.
6. **Honest Distinction of Intelligence:**
   - *Scripted Behavior:* Designer-written rules/triggers.
   - *Genuine Learning:* Agent value/prediction models updated from experience that demonstrably shift policy under identical states.
   - *Emergence:* Macro/social patterns arising from multi-agent interaction without being explicitly scripted.
   - Never claim "unlimited intelligence" or use `eval()` / arbitrary code execution for agent-discovered rules.
7. **Deterministic RNG Isolation:** Give new agent cognitive/learning modules per-agent RNG streams derived from a stable seed so they do not perturb the global `World.rng` sequence unexpectedly.
8. **Incremental Workflow:** Implement one coherent subsystem per session -> run `pytest` / unit tests -> verify accounting & pickle round-trip -> benchmark performance -> stop and report before starting the next phase.

---

## 4. File Index for Cline
Read only the file needed for your active task to save context window:
- `01_CALIBRATION_AND_AUDIT_BASELINE.md` — Existing architecture map, audit findings, and macro calibration / causal KB reference data (with integration warnings).
- `02_PHASE_1_ACCOUNTING_LEDGER.md` — Completed Phase 1 specification, invariants, and verification rules.
- `03_PHASE_2_ORGANIC_ECONOMY_AND_MARKETS.md` — Supply chains, goods elasticity, contracts, weighted CPI, value-added GDP, removing scripted unlocks.
- `04_PHASE_3_EPISODIC_MEMORY.md` — Bounded episodic & semantic memory (`systems/agents/memory.py`).
- `05_PHASE_4_KNOWLEDGE_GRAPH_AND_DISCOVERY.md` — Property multigraph, provenance, hypothesis formation, safe rule composition (`systems/agents/knowledge.py`).
- `06_PHASE_5_BDI_GOAP_AND_LEARNING.md` — BDI goals, bounded beam-search GOAP planner, contextual RL (`goals.py`, `planner.py`, `learning.py`).
- `07_PHASE_6_EXPERIMENTATION_AND_INNOVATION.md` — Cost- and risk-bearing hypothesis experiments (`systems/agents/experiments.py`).
- `08_PHASE_7_SOCIAL_GRAPH_AND_EMERGENT_INSTITUTIONS.md` — Sparse trust/reciprocity network, multi-agent contracts & organizations (`systems/agents/social.py`).
- `09_PHASE_8_FAMILY_AND_INTERGENERATIONAL_TRANSMISSION.md` — Kinship/life-cycle prerequisite, parent-child teaching, apprenticeships, archives, cultural drift/loss (`systems/agents/family.py`).
- `10_PHASE_9_OBSERVABILITY_MIGRATION_AND_BENCHMARKS.md` — Observation UI panels, multi-seed emergence validation, 140-citizen stress benchmarks, final cleanup.
