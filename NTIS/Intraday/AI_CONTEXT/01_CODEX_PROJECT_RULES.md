# NTIS Intraday - CODEX PROJECT RULES
Version: 1.0
Status: FROZEN

---

# PROJECT MODE

This is a production implementation project.

Architecture is frozen.

Business rules are frozen.

Documentation follows verified implementation.

Do not redesign architecture.

Do not redesign business rules.

---

# WORKSPACE

Workspace Root

E:\NSE_Daily_Analysis\NTIS\Intraday

This workspace is the ONLY authoritative source.

Only modify files inside this workspace.

Never modify files outside this workspace.

---

# EXTERNAL PROJECTS

Do NOT access:

• NTIS EOD project source
• Parent folders
• Sibling folders
• Other workspaces

Runtime folders referenced by configuration may be READ by production code only.

Do not modify runtime data unless explicitly instructed.

---

# GIT POLICY

Git is DISABLED.

Never use:

git status
git diff
git log
git fetch
git pull
git push
git merge
git rebase
git checkout
git switch
git cherry-pick
git branch
git blame
git show
git stash

Do not compare with GitHub.

Do not compare with remote repositories.

Treat the LOCAL WORKSPACE as the only source of truth.

Ignore any logged-in Git account.

---

# IMPLEMENTATION MODE

Modify existing production modules only.

Do not create duplicate engines.

Do not create duplicate production files.

Do not create backup copies.

Do not create experimental implementations.

Do not create placeholder implementations.

Complete ONE production module at a time.

Preserve existing public APIs unless explicitly required.

Preserve backward compatibility whenever possible.

---

# CONFIGURATION

Always use:

intraday_settings.ini

config_loader.py

Never hardcode filesystem paths.

Never introduce new configuration files unless explicitly instructed.

---

# TESTING

Only run the requested production module.

Do not execute unrelated modules.

Do not modify production data.

Do not regenerate reports unless requested.

If testing cannot continue,

STOP

and report the blocker.

---

# MISSING DEPENDENCIES

If any required production dependency is missing,

STOP IMMEDIATELY.

Return ONLY:

Exact missing production file.

Do not guess.

Do not infer.

Do not recreate missing production code.

Do not search outside the workspace.

---

# OUTPUT FORMAT

Return ONLY:

1. Replacement production file

2. Exact production path

3. Test command

Nothing else unless requested.

---

# DOCUMENTATION

Documentation follows implementation.

Never update documentation before implementation is verified.

Never recreate existing documentation.

Apply implementation deltas only.

---

# IMPLEMENTATION ORDER

Follow the frozen checkpoint.

Do not change implementation order unless instructed.

Current Bundle:

Bundle 02

1. pattern_statistics_engine.py

2. intraday_intelligence_loader.py

3. intraday_intelligence_query.py

4. intraday_historical_replay_engine.py

5. intraday_dashboard.py (if required)

---

# DASHBOARD

Preserve approved dashboard design.

Do not redesign UI.

Do not change layout unless explicitly instructed.

---

# STOP CONDITIONS

Immediately stop if:

• Required production dependency is missing.

• Workspace does not contain required module.

• Required configuration file is missing.

• Implementation would violate frozen architecture.

Report ONLY the exact blocker.

---

END OF RULES