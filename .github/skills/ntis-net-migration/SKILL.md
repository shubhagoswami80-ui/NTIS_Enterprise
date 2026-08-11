---
name: ntis-net-migration
user-invocable: true
description: "Refactor existing NTIS engineering utilities into the NET Engineering Toolkit using a one-file-at-a-time migration workflow."
---

# NTIS NET Migration Skill

## Objective

Migrate existing NTIS engineering utilities into the NET Engineering Toolkit (NET).

The goal is to consolidate engineering utilities without changing production business logic.

---

# Project Scope

Read from:

E:\NSE_Daily_Analysis\NTIS

Write to:

E:\NSE_Daily_Analysis\NET_Workspace

NET source destination:

E:\NSE_Daily_Analysis\NET_Workspace\Source

---

# STRICT EXCLUSIONS

Never read, scan, analyze, compare, index, modify or refactor anything under:

- Intraday/
- Archive/
- Output/
- AI_CONTEXT/
- Documentation/
- .venv/
- __pycache__/

Treat these folders as if they do not exist.

Ignore every import, dependency and reference originating from these folders.

---

# IGNORE FILES

Ignore any file containing:

_old
_org
_original
_backup
_bak
_copy
copy
backup
temp
tmp
draft
test_copy

Treat these files as non-existent.

---

# BUSINESS RULES

Never modify:

- Trading logic
- Business rules
- Scoring rules
- Pattern rules
- Historical calculations
- Repository logic

Refactor structure only.

---

# WORKFLOW

Always perform exactly one migration at a time.

For every engineering tool:

1. Read one source file.
2. Understand the existing implementation.
3. Refactor into NET architecture.
4. Improve code quality only.
5. Preserve behaviour.
6. Validate syntax.
7. Save the replacement module into NET_Workspace.
8. Stop that migration.

Immediately continue with the next engineering utility unless a real blocking error occurs.

Never ask for confirmation between files.

---

# OUTPUT

Generate:

One replacement Python module.

When requested:

Create a ZIP bundle for that module.

---

# DO NOT

Do not redesign architecture.

Do not create duplicate implementations.

Do not invent new business logic.

Do not modify production NTIS files.

Do not modify CSV outputs unless required for compatibility.

---

# NET TARGET STRUCTURE

NET_Workspace/

Source/

auditor/

project_scanner.py

dependency_analyzer.py

consolidation_analyzer.py

runtime_analyzer.py

pipeline_analyzer.py

report_builder.py

health_analyzer.py

NTIS_EOD_Project_Auditor.py

---

# SUCCESS CRITERIA

The migration is complete when:

- Every engineering utility has been migrated.
- No duplicate utilities remain.
- All migrated modules compile successfully.
- Production behaviour remains unchanged.
- NET is ready to replace the legacy engineering utilities.

At that point, stop.