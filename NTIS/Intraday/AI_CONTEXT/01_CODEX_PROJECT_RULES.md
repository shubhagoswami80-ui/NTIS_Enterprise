# NTIS Intraday - CODEX PROJECT RULES
Version: 2.0
Status: FROZEN & SYNCHRONIZED

---

# FROZEN GOVERNANCE RULES

1. PROJECT BOUNDARY
Primary implementation boundary: E:\NSE_Daily_Analysis\NTIS\Intraday. NTIS_Intraday is the authoritative Intraday implementation area.

2. EOD ISOLATION
EOD is a separate system. EOD CODE is OUT OF SCOPE for NTIS_Intraday implementation. EOD output data may be consumed only where an explicit NTIS_Intraday input contract requires it. Do not modify EOD implementation as part of Intraday work.

3. GIT GOVERNANCE
The current NTIS_Intraday implementation workflow does NOT use Git for development execution. Do not run Git commands unless explicitly authorized.

4. BACKUP / ALTERNATE FILE ISOLATION
Backup and alternate files are NOT production source. Exclude files matching `*.bak`, `*.backup`, `*.bkp`, `*.orig`, `*.old`, `*.tmp`, `*.temp`, `*_backup*`, `*_bkp*`, `*_orig*`, `*_old*` from discovery.

5. ENVIRONMENT / CACHE ISOLATION
Exclude `.venv`, `venv`, `env`, `ENV`, `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, node_modules, IDE caches, temporary caches, unrelated ZIPs, and logs. Do not modify dependencies.

6. DASHBOARD GOVERNANCE
The dashboard is a CONSUMER OF INTELLIGENCE. It must not become a competing intelligence engine. Dashboard code must not independently recreate scoring, probability, confidence, pattern identity, Business Pattern identity, learning, calibration, repository intelligence, outcome logic, or trading rules.

7. NO DUPLICATE ENGINES
Do not create competing or duplicate scoring, probability, confidence, pattern, pattern statistics, learning, calibration, replay, outcome, repository, or executive decision engines.

8. REPLAY READ-ONLY
Historical Replay is strictly READ-ONLY. Replay must not mutate repository, learning memory, calibration, historical snapshots, historical outcomes, Business Pattern IDs, or Pattern IDs.

9. HISTORICAL INTEGRITY
Historical intelligence must remain date-specific. Never silently substitute today's repository state for a historical state. Never mix historical dates or replace historical probability/confidence with today's values.

10. STOCK-SPECIFIC INTELLIGENCE
Stock-level historical intelligence must remain tied to the selected stock. Do not present another stock's evidence as evidence for the selected stock.

11. PATTERN-SPECIFIC INTELLIGENCE
Pattern-level intelligence must remain distinct from stock-level intelligence. Preserve the existing identity relationship between Pattern ID, Business Pattern ID, Pattern DNA, and Pattern Fingerprint.

12. NO FABRICATED INTELLIGENCE
Never fabricate probabilities, confidence, historical win rates, occurrences, outcomes, PnL, evidence levels, support, resistance, sector strength, risk/reward, entry, stop loss, target, Pattern IDs, or Business Pattern IDs. If unavailable, display an explicit unavailable state.

13. RAW DATA IS NOT THE PRODUCT
The normal trader-facing Executive interface must not become a raw-data display. Raw OI, volume, PDNA, fingerprints, repository keys, and engine internals are supporting/traceability information. Primary product is: WHAT → WHY → HISTORICAL EVIDENCE → DECISION.

14. DECISION-MAKER PRINCIPLE
NTIS_Intraday is a Stock-Specific Intraday Trading Intelligence + Decision-Maker System. The Executive interface helps answer what the stock is doing, what NTIS signals, historical action, relevant pattern evidence, evidence strength, market context, risk/reward, recommendation, and WHY.

15. MISSING PRODUCER RULE
If a required intelligence field is not supplied by an authoritative producer, do not recreate it inside the dashboard. Report the missing producer/field.

16. FROZEN ARCHITECTURE
Architecture is frozen unless explicitly authorized. Do not redesign architecture to simplify an individual task.

17. VALIDATION BEFORE ACCEPTANCE
Production functionality requires syntax/import validation, runtime validation, historical validation, read-only validation, regression validation, and decision-maker validation.

18. DOCUMENTATION SYNCHRONIZATION
Documentation must remain synchronized with architecture, implementation, dependencies, file boundaries, governance, validation results, production status, and remaining roadmap.

19. NO UNAUTHORIZED SCOPE EXPANSION
Do not expand a task merely because additional data/modules are available. Implement only approved tasks.

20. PROGRESSIVE DISCLOSURE
The dashboard follows Trader-First, Decision-First, Progressive Disclosure. Normal Executive interface shows the decision and its evidence first; technical details remain available through appropriate advanced/traceability areas.

---

# FIVE-LAYER IMPLEMENTATION STATUS

- Task 1 (Replay Validation): PASS
- Task 2 (Historical Replay Browser): PASS
- Task 3 (Stock Intelligence History): PASS
- Task 4 (Pattern Intelligence History): PASS
- Task 5 (Executive Dashboard Intelligence): PASS

Production Candidate Audit Status: PRODUCTION CANDIDATE — PASS (Blocking Defects: NONE, Non-Blocking Items: NONE).

---

END OF RULES