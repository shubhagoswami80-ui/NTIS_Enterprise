# NTIS_Intraday Scanner Changelog

---

## Version 2.2

### Engineering Metadata

- Introduced Intraday_engineering_metadata.json as the canonical engineering metadata model.
- Replaced architecture_map.json as the primary engineering artifact.

### Documentation Generation

Implemented automatic generation of:

- 04_MODULE_DEPENDENCY_MAP.md
- 16_MODULE_IMPLEMENTATION_REGISTRY.md
- 17_RUNTIME_OUTPUT_REGISTRY.md
- 18_INTELLIGENCE_DEPENDENCY_GRAPH.md
- 21_MODULE_CALL_GRAPH.md

### AI Context

Implemented automatic generation of:

- project_summary.json
- module_registry.json
- dependency_graph.json
- runtime_registry.json
- intelligence_index.json

### Scanner Architecture

Scanner responsibilities remain:

- Module Discovery
- Dependency Discovery
- Runtime Discovery
- Intelligence Discovery
- Dashboard Discovery

Scanner remains READ ONLY.

### Configuration

Added:

config/documentation_rules.json

config/module_templates.json

Configuration is now externalized from generator logic.

### Engineering Rules

Engineering metadata is the single source of truth.

All documentation is generated.

Manual edits to generated documentation are discouraged.

### Status

Production Ready