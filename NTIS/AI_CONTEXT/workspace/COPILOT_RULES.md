# NTIS EOD - Copilot Coding Rules

=========================================================
PROJECT
=========================================================

Project: NTIS EOD

Work ONLY on the active NTIS EOD production implementation.

=========================================================
WORKSPACE SCOPE
=========================================================

Editable

- Root production Python modules (*.py)
- analyzers/
- Config/
- EOD_Dashboard/
- replay/
- similarity_core_clean/
- Tools/

=========================================================
PROTECTED AREAS
=========================================================

Never read.

Never search.

Never index.

Never reference.

Never compare.

Never modify.

Treat these folders as if they do not exist.

Folders:

- Intraday/
- Archive/

=========================================================
IGNORE NON-PRODUCTION FILES
=========================================================

Ignore any backup, copied, temporary, archived,
draft or historical files.

Never read or modify files containing:

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

Examples:

config_old.py
app_org.py
runtime_backup.py
history_copy.py
module.tmp
analysis.draft.py

Treat these files as non-existent.

=========================================================
DOCUMENTATION
=========================================================

Do NOT automatically read:

AI_CONTEXT/
Documentation/

Do not open documentation unless I explicitly request:

- documentation work
- architecture review
- business rule review

=========================================================
GENERATED OUTPUT
=========================================================

Output/

Contains runtime-generated files.

Read or write only when required by the current implementation.

Do not manually modify generated output files unless explicitly requested.

=========================================================
CODING RULES
=========================================================

Architecture is frozen.

Business rules are frozen.

Modify existing production files whenever possible.

Avoid creating new files unless explicitly requested.

Do not create duplicate implementations.

Preserve backward compatibility.

Keep code changes minimal and localized.

If a requested task appears outside the defined workspace,
stop and ask for confirmation before proceeding.

Never redesign completed functionality.