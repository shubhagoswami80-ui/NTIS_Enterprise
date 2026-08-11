---
name: create-skill
user-invocable: true
description: "Create a new SKILL.md file for workspace or user-scoped VS Code agent customization."
---

# Create a `SKILL.md`

This skill guides you through creating a new `SKILL.md` file for VS Code Copilot customization.

## When to use

- You want to add a reusable, multi-step workspace or user-level skill.
- You need a standard template for `SKILL.md` frontmatter and structure.
- You want to document the expected workflow, triggers, and validation checks for a skill.

## What this produces

- A `SKILL.md` file containing:
  - YAML frontmatter with `name`, `user-invocable`, and `description`
  - a clear purpose statement
  - step-by-step creation guidance
  - completion checks and sample prompts

## Steps to create a `SKILL.md`

1. Choose the scope:
   - Workspace: put the file under `.github/skills/<skill-name>/SKILL.md`
   - User-level: put the file under `{{VSCODE_USER_PROMPTS_FOLDER}}/<skill-name>/SKILL.md`

2. Define the required frontmatter:
   - `name`: the skill identifier
   - `user-invocable`: `true` if users should trigger it directly
   - `description`: a concise, searchable summary

3. Write the body:
   - why the skill exists
   - when to use it
   - the exact workflow or checklist
   - validation criteria or expected output

4. Save and verify:
   - confirm the file exists in the chosen folder
   - ensure YAML is valid and the description is meaningful
   - use precise trigger language in the description

## Example prompts to use this skill

- `Create a SKILL.md for a new code cleanup workflow`
- `Show me the template for a workspace skill`
- `Guide me through building a Copilot skill file`

## Validation

- The file contains valid YAML frontmatter.
- The `description` is specific enough for the agent to discover the skill.
- The body includes a clear step-by-step workflow and checks.
- The location matches the chosen scope.
