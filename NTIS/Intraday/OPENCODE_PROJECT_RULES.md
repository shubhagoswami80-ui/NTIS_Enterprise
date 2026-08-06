# NTIS Intraday - OpenCode Project Rules

## Workspace

E:\NSE_Daily_Analysis\NTIS\Intraday

---

# Mandatory AI Safety Workflow

## Default Mode

AI operates in:

ANALYSIS ONLY MODE

AI must NOT directly modify, overwrite, rename, delete, or replace any production file.

Before any code change, AI must provide:

1. Impact Analysis

2. Files affected

3. Functions affected

4. Estimated lines changed

5. Risk level:
   - Low
   - Medium
   - High

6. Change method:
   - Insert only
   - Function replacement
   - Full file replacement

7. Backward compatibility impact

---

## Approval Gate

After impact analysis:

STOP.

Do not generate code.

Do not apply changes.

Wait for explicit user approval.

Allowed approvals:

APPROVE INSERTION

APPROVE FUNCTION CHANGE

APPROVE FULL FILE REPLACEMENT

Without explicit approval:

NO FILE MODIFICATION IS ALLOWED.

---

# Minimum Change Principle

Always prefer:

- Smallest possible code change.
- Function insertion.
- Local logic enhancement.
- Existing API preservation.

Avoid:

- Full file rewrites.
- Refactoring stable code.
- Formatting changes.
- Variable renaming.
- Moving functions.
- Architecture changes.

If more than 10% of a production file requires modification:

Stop and explain why.

---

# Read Before Every Task

1. AI_CONTEXT/00_START_HERE.md
2. AI_CONTEXT/01_CODEX_PROJECT_RULES.md
3. README_FOR_CODEX.md

Read additional AI_CONTEXT documents only if required.

---

# Development Rules

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

# Production Rules

- Never create duplicate production files.
- Never create backup files.
- Never rename production modules.
- Never modify OCR modules unless explicitly instructed.
- Keep runtime folders unchanged.
- Never replace a production file without approval.

---

# Implementation Rules

Every production change must identify:

1. Existing behaviour.
2. Required change.
3. Reason for change.
4. Expected impact.
5. Rollback approach.

Production logic must remain unchanged unless specifically approved.

---

# Testing Rules

Every production implementation must include:

1. Import test.

2. Functional test.

3. Production execution path.

4. Output validation.

---

# Completion Rules

Before considering a task complete:

Confirm:

- Modified files.
- Reason for modification.
- Test result.
- Remaining risks.
- Next implementation step.