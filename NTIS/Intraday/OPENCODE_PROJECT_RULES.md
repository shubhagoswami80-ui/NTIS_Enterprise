# NTIS Intraday - OpenCode Project Rules

## Workspace

E:\NSE_Daily_Analysis\NTIS\Intraday

---

## Read Before Every Task

1. AI_CONTEXT/00_START_HERE.md
2. AI_CONTEXT/01_CODEX_PROJECT_RULES.md
3. README_FOR_CODEX.md

Read additional AI_CONTEXT documents only if required.

---

## Development Rules

- Development mode only.
- Preserve frozen architecture.
- No Git operations.
- No architecture redesign.
- Modify the minimum number of production files.
- One production capability at a time.
- Preserve existing public APIs.
- Review direct dependencies before modifying any module.
- If a blocker exists, stop and report it.
- Never invent missing business logic.
- Restore existing implementations before reconstructing them.

---

## Production Rules

- Never create duplicate production files.
- Never create backup files.
- Never rename production modules.
- Never modify OCR modules unless explicitly instructed.
- Keep runtime folders unchanged.

---

## Testing Rules

Every production implementation must include:

1. Import test.
2. Functional test.
3. Production execution path.