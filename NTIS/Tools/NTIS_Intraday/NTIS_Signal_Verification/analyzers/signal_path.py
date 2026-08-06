from pathlib import Path
import ast
import json


class SignalPathAnalyzer:

    SIGNAL_KEYWORDS = {
        "BUY",
        "SELL",
        "HOLD",
        "ENTRY",
        "EXIT",
        "TARGET",
        "STOPLOSS",
        "SIGNAL"
    }

    FUNCTION_HINTS = {
        "signal",
        "entry",
        "exit",
        "decision",
        "trade",
        "buy",
        "sell",
        "recommend"
    }

    def __init__(self, config, output):

        self.config = config

        self.output = Path(output)

        self.code_root = Path(config["code_root"])

        self.results = []

    def run(self):

        print("Scanning Signal Paths...")

        for file in self.code_root.rglob("*.py"):

            if "__pycache__" in file.parts:
                continue

            self.scan_file(file)

        self.save()

        print(f"Signal Paths : {len(self.results)}")

    def scan_file(self, file):

        try:

            source = file.read_text(
                encoding="utf-8",
                errors="ignore"
            )

            tree = ast.parse(source)

        except Exception:

            return

        visitor = SignalVisitor(file)

        visitor.visit(tree)

        self.results.extend(visitor.results)

    def save(self):

        with open(

            self.output / "signal_execution_map.json",

            "w",

            encoding="utf-8"

        ) as f:

            json.dump(

                self.results,

                f,

                indent=4,

                ensure_ascii=False

            )


class SignalVisitor(ast.NodeVisitor):

    def __init__(self, file):

        self.file = file

        self.results = []

    def visit_FunctionDef(self, node):

        name = node.name.lower()

        matched = any(

            keyword in name

            for keyword in SignalPathAnalyzer.FUNCTION_HINTS

        )

        constants = []

        for child in ast.walk(node):

            if isinstance(child, ast.Constant):

                if isinstance(child.value, str):

                    text = child.value.upper()

                    for kw in SignalPathAnalyzer.SIGNAL_KEYWORDS:

                        if kw in text:

                            constants.append(kw)

        if matched or constants:

            self.results.append({

                "file": str(self.file),

                "function": node.name,

                "line": node.lineno,

                "signal_keywords":

                    sorted(list(set(constants)))

            })

        self.generic_visit(node)