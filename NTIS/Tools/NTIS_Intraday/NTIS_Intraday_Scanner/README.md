# NTIS_Intraday Scanner

## Purpose

The NTIS_Intraday Scanner is the engineering discovery tool for the NTIS_Intraday project.

It automatically scans the production codebase and runtime folders to generate engineering metadata, AI context, and project documentation.

The scanner is READ ONLY.

It never modifies production source code or business data.

---

## Project Structure

NTIS_Intraday_Scanner
│
├── config
│
├── scanners
│
├── generators
│
├── output
│
└── ntis_intraday_scanner.py

---

## Generated Outputs

### Engineering Metadata

output/Intraday_engineering_metadata.json

Single source of truth for all engineering metadata.

---

### Documentation

output/Documentation/

Automatically generated engineering documentation.

Do not edit manually.

---

### AI Context

output/AI_Context/

Structured JSON consumed by ChatGPT, Gemini, Claude, Codex and other AI systems.

---

## Execution

Run:

python ntis_intraday_scanner.py

---

## Workflow

Production Code
        │
        ▼
Module Scanner
Dependency Scanner
Dataflow Scanner
Intelligence Scanner
Dashboard Scanner
        │
        ▼
Intraday_engineering_metadata.json
        │
        ├── Documentation Generator
        │
        └── AI Context Generator

---

## Engineering Rules

The scanner is READ ONLY.

The scanner never modifies production modules.

The scanner never modifies runtime data.

All engineering documents are generated automatically.

Manual edits to generated documentation are not supported.

---

## Configuration

config/documentation_rules.json

Business classification rules.

config/module_templates.json

Module classification templates.

---

## Ownership

Project

NTIS_Intraday

Architecture

Frozen

Documentation

Auto Generated

Engineering Metadata

Intraday_engineering_metadata.json
