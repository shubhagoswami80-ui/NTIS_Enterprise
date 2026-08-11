# NTIS Intraday

# START HERE

Before performing any task, read the following documents IN ORDER.

1. 01_CODEX_PROJECT_RULES.md
2. 02_MASTER_CHECKPOINT.md
3. 03_PROJECT_ARCHITECTURE.md
4. 05_IMPLEMENTATION_SPECIFICATION.md
5. 04_IMPLEMENTATION_STATUS.md
6. 06_MODULE_CONTRACTS.md
7. 08_PROJECT_PROGRESS.md

After reading them:

- Resume the current implementation bundle.
- Continue from the latest completed capability.
- Preserve the frozen architecture.
- Preserve existing business rules.

Do NOT:

- Rediscover architecture.
- Redesign business rules.
- Rebuild an existing production module if an implementation already exists in the workspace.
- Create duplicate engines.
- Create duplicate production files.
- Rename production modules.
- Use Git unless explicitly instructed.

Implementation Rules:

- Review before implementation.
- Modify the minimum number of production files.
- Preserve existing public APIs unless explicitly instructed.
- Return one production replacement file at a time.
- Always provide:
  - Production file path
  - Import test
  - Functional test
- If a production blocker is found, stop and report it instead of inventing implementations.