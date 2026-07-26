"""
NTIS Similarity Core Dependency Map

Purpose:
    Dependency analysis for similarity_core_clean reconstruction.

Rules:
    - READ ONLY
    - No file movement
    - No deletion
    - No configuration changes

Target:
    similarity_core_clean

Outputs:
    KEEP_REQUIRED_FILES.csv
    ARCHIVE_FILES.csv
    UNKNOWN_FILES.csv
"""

from pathlib import Path
import ast
import csv


BASE_DIR = Path(__file__).resolve().parent

# Clean reconstruction target
SIMILARITY_CORE = BASE_DIR / "similarity_core_clean"

OUTPUT_KEEP = BASE_DIR / "KEEP_REQUIRED_FILES.csv"
OUTPUT_ARCHIVE = BASE_DIR / "ARCHIVE_FILES.csv"
OUTPUT_UNKNOWN = BASE_DIR / "UNKNOWN_FILES.csv"


ENTRY_POINTS = [
    "production_runtime.py",
    "eod_data_resolution_activation_check_v17.py",
    "eod_data_resolution_core_v17.py",
]


def get_python_files():

    files = {}

    for path in SIMILARITY_CORE.rglob("*.py"):

        if "__pycache__" not in str(path):

            files[path.name] = path

    return files


def extract_imports(file_path):

    imports = []

    try:

        source = file_path.read_text(
            encoding="utf-8",
            errors="ignore"
        )

        tree = ast.parse(source)

        for node in ast.walk(tree):

            if isinstance(node, ast.Import):

                for item in node.names:
                    imports.append(
                        item.name.split(".")[-1] + ".py"
                    )

            elif isinstance(node, ast.ImportFrom):

                if node.module:

                    imports.append(
                        node.module.split(".")[-1] + ".py"
                    )

    except Exception:
        pass

    return imports


def build_dependency_graph(files):

    graph = {}

    for name, path in files.items():

        graph[name] = []

        for dependency in extract_imports(path):

            if dependency in files:

                graph[name].append(dependency)

    return graph


def resolve_dependencies(graph, start):

    visited = set()

    def walk(node):

        if node in visited:
            return

        visited.add(node)

        for child in graph.get(node, []):

            walk(child)

    walk(start)

    return visited


def write_csv(path, rows):

    with open(
        path,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.writer(file)

        writer.writerow(
            [
                "File",
                "Classification"
            ]
        )

        writer.writerows(rows)


def main():

    print("=" * 60)
    print("NTIS CLEAN SIMILARITY CORE DEPENDENCY MAP")
    print("=" * 60)

    files = get_python_files()

    print(
        "Python Files Found:",
        len(files)
    )

    graph = build_dependency_graph(files)

    required = set()

    for entry in ENTRY_POINTS:

        if entry in graph:

            print(
                "Tracing:",
                entry
            )

            required |= resolve_dependencies(
                graph,
                entry
            )


    keep = []
    archive = []
    unknown = []


    for name in sorted(files):

        if name in required:

            keep.append(
                [
                    name,
                    "KEEP_REQUIRED"
                ]
            )

        elif any(
            keyword in name.lower()
            for keyword in
            [
                "_old",
                "_backup",
                "_copy",
                "_orig"
            ]
        ):

            archive.append(
                [
                    name,
                    "ARCHIVE_CANDIDATE"
                ]
            )

        else:

            unknown.append(
                [
                    name,
                    "UNKNOWN_REVIEW"
                ]
            )


    write_csv(
        OUTPUT_KEEP,
        keep
    )

    write_csv(
        OUTPUT_ARCHIVE,
        archive
    )

    write_csv(
        OUTPUT_UNKNOWN,
        unknown
    )


    print("-" * 60)
    print("RESULT")
    print("-" * 60)

    print("KEEP:", len(keep))
    print("ARCHIVE:", len(archive))
    print("UNKNOWN:", len(unknown))

    print()
    print("Reports:")
    print(OUTPUT_KEEP)
    print(OUTPUT_ARCHIVE)
    print(OUTPUT_UNKNOWN)


if __name__ == "__main__":
    main()