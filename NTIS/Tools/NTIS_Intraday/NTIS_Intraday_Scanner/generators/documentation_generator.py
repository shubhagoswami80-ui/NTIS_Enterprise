from pathlib import Path
import json

DOCS = [
    "04_MODULE_DEPENDENCY_MAP.md",
    "16_MODULE_IMPLEMENTATION_REGISTRY.md",
    "17_RUNTIME_OUTPUT_REGISTRY.md",
    "18_INTELLIGENCE_DEPENDENCY_GRAPH.md",
    "21_MODULE_CALL_GRAPH.md",
]


class DocumentationGenerator:

    def __init__(self, metadata_file, output_root):
        self.metadata_file = Path(metadata_file)
        self.output_root = Path(output_root)
        self.output_root.mkdir(parents=True, exist_ok=True)

        with self.metadata_file.open("r", encoding="utf-8") as f:
            self.meta = json.load(f)

    def generate(self):
        self._module_registry()
        self._dependency_map()
        self._runtime_registry()
        self._intelligence_graph()
        self._call_graph()

    def _write(self, filename, text):
        (self.output_root / filename).write_text(
            text,
            encoding="utf-8"
        )

    def _module_registry(self):

        lines = [
            "# Module Implementation Registry",
            "",
            "| Module | Classes | Functions |",
            "|---|---|---|",
        ]

        for m in self.meta["folder_architecture"]["code"]:
            lines.append(
                f"| {Path(m['file']).name} | "
                f"{len(m['classes'])} | "
                f"{len(m['functions'])} |"
            )

        self._write(
            "16_MODULE_IMPLEMENTATION_REGISTRY.md",
            "\n".join(lines)
        )

    def _dependency_map(self):

        lines = [
            "# Module Dependency Map",
            "",
            "| Module | Imports |",
            "|---|---|",
        ]

        for d in self.meta["dependencies"]:
            lines.append(
                f"| {Path(d['file']).name} | "
                f"{', '.join(d['imports'])} |"
            )

        self._write(
            "04_MODULE_DEPENDENCY_MAP.md",
            "\n".join(lines)
        )

    def _runtime_registry(self):

        lines = [
            "# Runtime Output Registry",
            ""
        ]

        for f in self.meta["folder_architecture"]["data"]:
            lines.append(f"- {f}")

        self._write(
            "17_RUNTIME_OUTPUT_REGISTRY.md",
            "\n".join(lines)
        )

    def _intelligence_graph(self):

        lines = [
            "# Intelligence Dependency Graph",
            ""
        ]

        for item in self.meta["intelligence"]:
            lines.append(
                f"## {Path(item['file']).name}"
            )
            lines.append(
                ", ".join(item["keywords"])
            )
            lines.append("")

        self._write(
            "18_INTELLIGENCE_DEPENDENCY_GRAPH.md",
            "\n".join(lines)
        )

    def _call_graph(self):

        lines = [
            "# Module Call Graph",
            "",
            "| Module | Imported Modules |",
            "|---|---|",
        ]

        for d in self.meta["dependencies"]:
            imports = [
                x for x in d["imports"]
                if x
            ]

            lines.append(
                f"| {Path(d['file']).name} | "
                f"{', '.join(imports)} |"
            )

        self._write(
            "21_MODULE_CALL_GRAPH.md",
            "\n".join(lines)
        )