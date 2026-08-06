from pathlib import Path
import ast
import json


class RepositoryUsageAnalyzer:

    KEYWORDS = {

        "repository",

        "business_pattern_id",

        "pattern_fingerprint",

        "historical",

        "evidence",

        "replay",

        "learning",

        "lifecycle",

        "probability"

    }

    def __init__(self, config, output):

        self.code_root = Path(config["code_root"])

        self.output = Path(output)

        self.results = []

    def run(self):

        print("Scanning Repository Usage...")

        for file in self.code_root.rglob("*.py"):

            if "__pycache__" in file.parts:

                continue

            self.scan(file)

        self.save()

        print(f"Repository Modules : {len(self.results)}")

    def scan(self, file):

        try:

            tree = ast.parse(

                file.read_text(

                    encoding="utf-8",

                    errors="ignore"

                )

            )

        except Exception:

            return

        imports = []

        names = set()

        for node in ast.walk(tree):

            if isinstance(node, ast.Import):

                for alias in node.names:

                    imports.append(alias.name)

            elif isinstance(node, ast.ImportFrom):

                if node.module:

                    imports.append(node.module)

            elif isinstance(node, ast.Name):

                names.add(node.id.lower())

        matched = sorted(

            [

                x

                for x in names

                if x in self.KEYWORDS

            ]

        )

        if matched or imports:

            self.results.append({

                "file": str(file),

                "repository_keywords": matched,

                "imports": imports

            })

    def save(self):

        with open(

            self.output / "repository_usage.json",

            "w",

            encoding="utf-8"

        ) as f:

            json.dump(

                self.results,

                f,

                indent=4,

                ensure_ascii=False

            )