# NTIS Intraday
# IMPLEMENTATION SPECIFICATION

Version : 1.0
Status  : FROZEN

------------------------------------------------------------
PURPOSE
------------------------------------------------------------

This document is the authoritative implementation
specification for NTIS Intraday.

All production implementation shall follow this
specification.

------------------------------------------------------------
IMPLEMENTATION MODE
------------------------------------------------------------

Production Implementation

Architecture Frozen

Business Rules Frozen

Configuration Driven

One Production Module at a Time

------------------------------------------------------------
IMPLEMENTATION ORDER
------------------------------------------------------------

Follow the current bundle sequence defined in

02_MASTER_CHECKPOINT.md

and

04_IMPLEMENTATION_STATUS.md

Do not change implementation order
unless explicitly instructed.

------------------------------------------------------------
PRODUCTION RULES
------------------------------------------------------------

Modify existing production modules only.

No duplicate files.

No duplicate engines.

No placeholder implementations.

No experimental implementations.

Preserve backward compatibility.

Preserve public APIs unless
explicitly required.

------------------------------------------------------------
DEPENDENCIES
------------------------------------------------------------

Read only direct production dependencies.

Never search outside the workspace.

Never infer missing production modules.

------------------------------------------------------------
TESTING
------------------------------------------------------------

Every completed module shall be

Backup

↓

Replace

↓

Run Test

↓

Verify

↓

Proceed

------------------------------------------------------------
DOCUMENTATION
------------------------------------------------------------

Documentation follows verified implementation.

Implementation always has priority.

------------------------------------------------------------
AUTHORITATIVE REFERENCES
------------------------------------------------------------

01_CODEX_PROJECT_RULES.md

02_MASTER_CHECKPOINT.md

03_PROJECT_ARCHITECTURE.md

04_IMPLEMENTATION_STATUS.md

06_MODULE_CONTRACTS.md